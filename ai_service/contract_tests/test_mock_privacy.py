"""Synthetic retention and no-disclosure checks; no real diagnostic payloads."""
from datetime import datetime, timedelta, timezone
import io
import json
import logging
import unittest

from agentfit_ai.http_service import create_app
from contract_mock.gateway import synthetic_analysis
from contract_mock.schema import ContractError
from contract_mock.server import create_mock_app
from contract_mock.store import MockStore
from test_mock_http import client, DOCUMENT
from test_mock_analysis_lifecycle import create_project, analyze


def attempt(store, project_id):
    return store.begin('owner-a', project_id, {'kind': 'TEXT', 'displayName': None,
        'byteSize': 20, 'characterCount': 20, 'pageCount': None})


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.now = [datetime(2026, 9, 30, tzinfo=timezone.utc)]
        self.store = MockStore(clock=lambda: self.now[0])
        self.project_id = self.store.create('owner-a', 'Plan')['project']['id']

    def failed(self, project_id):
        value = attempt(self.store, project_id)
        self.store.fail('owner-a', project_id, value['id'], 'AI_UNAVAILABLE')
        return value['id']

    def test_failure_diagnostic_expires_at_exactly_seven_days_from_failure(self):
        failed_id = self.failed(self.project_id)
        self.now[0] += timedelta(days=1)
        self.store.record_failed_diagnostic('owner-a', self.project_id, failed_id, b'synthetic-failure')
        self.now[0] += timedelta(days=6, microseconds=-1)
        self.assertEqual(self.store.purge_diagnostics(), 0)
        self.assertEqual(self.store.diagnostic_count(), 1)
        self.now[0] += timedelta(microseconds=1)
        self.assertEqual(self.store.purge_diagnostics(), 1)
        self.assertEqual(self.store.diagnostic_count(), 0)
        with self.assertRaises(ContractError):
            self.store.record_failed_diagnostic('owner-a', self.project_id, failed_id, b'late')

    def test_success_and_processing_diagnostics_are_rejected(self):
        value = attempt(self.store, self.project_id)
        with self.assertRaises(ContractError):
            self.store.record_failed_diagnostic('owner-a', self.project_id, value['id'], b'synthetic')
        result = synthetic_analysis(DOCUMENT, value['document']['id'])
        self.store.finish('owner-a', self.project_id, value['id'], result['profile'],
                          {k: result[k] for k in ('contract', 'fieldStates', 'questions')})
        with self.assertRaises(ContractError):
            self.store.record_failed_diagnostic('owner-a', self.project_id, value['id'], b'synthetic')
        self.assertEqual(self.store.diagnostic_count(), 0)

    def test_delete_cascades_only_its_diagnostics_and_blocks_late_write(self):
        a = self.failed(self.project_id)
        other = self.store.create('owner-a', 'Other')['project']['id']
        b = self.failed(other)
        self.store.record_failed_diagnostic('owner-a', self.project_id, a, b'first-synthetic')
        self.store.record_failed_diagnostic('owner-a', other, b, b'second-synthetic')
        self.store.delete('owner-a', self.project_id)
        self.assertEqual(self.store.diagnostic_count(), 1)
        with self.assertRaises(ContractError) as caught:
            self.store.record_failed_diagnostic('owner-a', self.project_id, a, b'late')
        self.assertEqual(caught.exception.code, 'PROJECT_NOT_FOUND')
        self.assertEqual(self.store.detail('owner-a', other)['latestAttempt']['id'], b)


class PrivacyHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_document_and_exception_are_absent_from_errors_storage_and_logs(self):
        store, output = MockStore(), io.StringIO()
        marker = 'synthetic-private-marker-789'
        def broken(document, document_id):
            raise RuntimeError(marker + document)
        app = create_mock_app(store=store, ai_app=create_app(internal_token='mock-internal',
            analyze=broken, analysis_mode='integrated-candidates'))
        handler = logging.StreamHandler(output)
        logging.getLogger().addHandler(handler)
        try:
            async with client(app) as http:
                p = await create_project(http)
                response = await analyze(http, p, marker.encode())
                self.assertEqual(response.status_code, 502)
                detail = (await http.get(f'/api/projects/{p}')).text
                for text in (response.text, detail, json.dumps(store._entries), output.getvalue()):
                    self.assertNotIn(marker, text)
                self.assertIsNone(store.detail('owner-a', p)['draft'])
        finally:
            logging.getLogger().removeHandler(handler)

    async def test_identified_credentials_in_persisted_inputs_are_rejected(self):
        store = MockStore()
        secret = 'api_key=synthetic-secret-value-123'
        async with client(create_mock_app(store=store)) as http:
            response = await http.post('/api/projects', json={'name': secret})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()['error']['code'], 'SENSITIVE_INPUT')
            p = await create_project(http)
            data = synthetic_analysis(DOCUMENT, 'doc_x')['profile']['data']
            data['domain'] = secret
            response = await http.patch(f'/api/projects/{p}/profile', json={'expectedVersion': 0, 'data': data})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(secret, json.dumps(store._entries))

    async def test_filename_is_decoded_and_invalid_sensitive_or_text_filename_rejected(self):
        async with client(create_mock_app()) as http:
            p = await create_project(http)
            url = f'/api/projects/{p}/analysis'
            response = await http.post(url, content=DOCUMENT, headers={
                'Content-Type': 'text/markdown', 'X-Document-Name': '%EA%B8%B0%ED%9A%8D.md'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['attempt']['document']['displayName'], '기획.md')
            for name, status in [('%GG', 400), ('bad%0Aname.md', 422), ('x' * 201, 422),
                                  ('api_key%3Dsynthetic-secret-value-123', 422)]:
                response = await http.post(url, content=DOCUMENT, headers={'Content-Type': 'text/markdown', 'X-Document-Name': name})
                self.assertEqual(response.status_code, status)
            response = await http.post(url, content=DOCUMENT, headers={'Content-Type': 'text/plain', 'X-Document-Name': 'name.txt'})
            self.assertEqual(response.status_code, 422)

    async def test_patch_write_failure_preserves_confirmed_and_project_version(self):
        store = MockStore()
        async with client(create_mock_app(store=store)) as http:
            p = await create_project(http)
            data = synthetic_analysis(DOCUMENT, 'doc_x')['profile']['data']
            first = await http.patch(f'/api/projects/{p}/profile', json={'expectedVersion': 0, 'data': data})
            data['frontend'] = ['Vue']
            store.fail_next_write = True
            failed = await http.patch(f'/api/projects/{p}/profile', json={'expectedVersion': 1, 'data': data})
            self.assertEqual(failed.status_code, 503)
            detail = (await http.get(f'/api/projects/{p}')).json()
            self.assertEqual(detail['confirmed'], first.json()['confirmed'])
            self.assertEqual(detail['project']['version'], 1)
