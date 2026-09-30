"""Versioned confirmation at the real ASGI boundary; no provider calls."""
import asyncio
from copy import deepcopy
import os
from threading import BoundedSemaphore
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agentfit_ai.http_service import create_app
from test_candidate_confirmation import DOCUMENT, DOCUMENT_ID, result


HEADERS = {'Authorization': 'Bearer synthetic-internal', 'X-Document-Id': DOCUMENT_ID,
           'X-Request-Id': 'REQ', 'X-Document-Kind': 'TEXT', 'Content-Type': 'text/plain',
           'X-AgentFit-Analysis-Contract': 'confirmation-v2'}


def draft():
    profile = result()['profile']
    states = {field: 'unknown' if value is None else 'suggested'
              for field, value in profile['data'].items()}
    states['frontend'] = 'unresolved'
    return {'contract': 'confirmation-v2', 'outcome': 'needs_confirmation', 'profile': profile,
            'fieldStates': states, 'error': 'REVIEW_CONFIRMATION_REQUIRED',
            'questions': [{'field': field, 'questionId': 'confirm_' + field,
                'reason': 'REVIEW_ISSUE' if state == 'unresolved' else 'CONFIRM_SUGGESTION'}
                for field, state in states.items() if state != 'unknown']}


class IntegratedHttpTests(unittest.TestCase):
    def send(self, outcome, *, mode='integrated-candidates'):
        client = TestClient(create_app(internal_token='synthetic-internal', analysis_mode=mode,
                                      analyze=lambda *_: outcome))
        return client.post('/internal/v1/analyze', content=DOCUMENT.encode(), headers=HEADERS)

    def test_v2_preserves_grounded_unresolved_and_empty_array_with_exact_questions(self):
        expected = draft()
        response = self.send(expected)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(expected, requestId='REQ'))
        self.assertEqual(response.json()['profile']['data']['frontend'], ['React'])
        self.assertEqual(response.json()['profile']['data']['external_integrations'], [])

    def test_contract_is_checked_after_auth_before_body_and_admission(self):
        slots = BoundedSemaphore(1)
        slots.acquire()
        with patch('agentfit_ai.http_service.BoundedSemaphore', return_value=slots):
            app = create_app(internal_token='synthetic-internal', analysis_mode='integrated-candidates')
        async def request(values, *, authorized=True):
            sent = []
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                     'method': 'POST', 'scheme': 'http', 'path': '/internal/v1/analyze',
                     'raw_path': b'/internal/v1/analyze', 'query_string': b'',
                     'headers': [(b'authorization', b'Bearer synthetic-internal' if authorized else b'wrong')] +
                                [(b'x-agentfit-analysis-contract', v) for v in values]}
            async def receive():
                raise AssertionError('body read before contract/admission')
            async def send(message):
                sent.append(message)
            await app(scope, receive, send)
            return sent[0]['status']
        for values in ([], [b'confirmation-v1'], [b'wrong'], [b'confirmation-v2'] * 2):
            with self.subTest(values=values):
                self.assertEqual(asyncio.run(request(values)), 428)
        self.assertEqual(asyncio.run(request([], authorized=False)), 401)

    def test_rejects_complete_v1_bad_evidence_questions_and_private_failure(self):
        invalid = []
        for mutate in (lambda d: d.update(contract='confirmation-v1'),
                       lambda d: d['questions'].pop(),
                       lambda d: d['questions'].append(d['questions'][0]),
                       lambda d: d['profile']['evidence']['frontend'][0].update(documentId='wrong')):
            value = deepcopy(draft())
            mutate(value)
            invalid.append(value)
        invalid += [{'outcome': 'complete', 'profile': result()['profile']},
                    {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'private response'},
                    {'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'}]
        for outcome in invalid:
            with self.subTest(outcome=outcome['outcome']):
                response = self.send(outcome)
                self.assertEqual(response.status_code, 502)
                self.assertNotIn('private response', response.text)
        failed = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'}
        self.assertEqual(self.send(failed).json(), dict(failed, requestId='REQ'))
        self.assertEqual(self.send(failed, mode='default').status_code, 502)

    def test_missing_either_key_rejects_before_worker_and_missing_sdk_is_503(self):
        client = TestClient(create_app(internal_token='synthetic-internal', analysis_mode='integrated-candidates'))
        for solar, nvidia in (('', 'synthetic-nvidia'), ('synthetic-solar', ''), (' ', 'synthetic-nvidia')):
            with self.subTest(solar=bool(solar), nvidia=bool(nvidia)), patch.dict(os.environ,
                    {'UPSTAGE_API_KEY': solar, 'NVIDIA_API_KEY': nvidia}), patch(
                    'agentfit_ai.http_service.run_analysis_process', side_effect=AssertionError('worker called')):
                response = client.post('/internal/v1/analyze', content=DOCUMENT.encode(), headers=HEADERS)
                self.assertEqual((response.status_code, response.json()), (503, {'error': 'MISSING_OR_INVALID_KEY'}))
        response = self.send({'error': 'INTEGRATED_RUNTIME_UNAVAILABLE'})
        self.assertEqual((response.status_code, response.json()), (503, {'error': 'INTEGRATED_RUNTIME_UNAVAILABLE'}))

    def test_mode_specific_timeout_env_matches_arguments_and_dispatch(self):
        for mode, value in (('default', 120), ('recoverable-solar', 120),
                            ('integrated-candidates', 1800), ('integrated-candidates', 3600)):
            with self.subTest(mode=mode, value=value), patch.dict(os.environ, {'AGENTFIT_REQUEST_TIMEOUT_SECONDS': str(value)}):
                create_app(analysis_mode=mode)
                create_app(analysis_mode=mode, request_timeout_seconds=value)
        for value in ('3601', 'abc', '1.0', '-1', '0', '00001'):
            with self.subTest(value=value), patch.dict(os.environ, {'AGENTFIT_REQUEST_TIMEOUT_SECONDS': value}), self.assertRaises(ValueError):
                create_app(analysis_mode='integrated-candidates')
        for value in (True, 3601, 0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                create_app(analysis_mode='integrated-candidates', request_timeout_seconds=value)
        seen = []
        async def worker(text, document_id, key, deadline, **options):
            seen.append((text, document_id, key, deadline - asyncio.get_running_loop().time(), options))
            return draft()
        with patch.dict(os.environ, {'UPSTAGE_API_KEY': 'synthetic-solar', 'NVIDIA_API_KEY': 'synthetic-nvidia',
                                    'AGENTFIT_ANALYSIS_MODE': 'integrated-candidates',
                                    'AGENTFIT_REQUEST_TIMEOUT_SECONDS': '1800'}), patch(
                'agentfit_ai.http_service.run_analysis_process', side_effect=worker):
            client = TestClient(create_app(internal_token='synthetic-internal'))
            response = client.post('/internal/v1/analyze', content=DOCUMENT.encode(), headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen[0][:3], (DOCUMENT, DOCUMENT_ID, 'synthetic-solar'))
        self.assertTrue(1790 < seen[0][3] <= 1800)
        self.assertEqual(seen[0][4], {'integrated_candidates': True, 'nvidia_key': 'synthetic-nvidia'})


if __name__ == '__main__':
    unittest.main()
