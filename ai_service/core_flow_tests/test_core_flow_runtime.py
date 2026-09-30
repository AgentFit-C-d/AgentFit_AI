"""Real SDK/worker to public mock confirmation; synthetic providers, loopback only."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import sys
import time
import unittest
from unittest.mock import patch

import httpx
import langextract  # This dedicated suite must fail if its optional SDK is absent.

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime_tests'))
sys.path.insert(0, str(ROOT / 'contract_tests'))

from contract_mock.schema import check
from contract_mock.store import MockStore
from test_integrated_service import Provider, service
from test_integrated_runtime import NVIDIA_KEY, SOLAR_KEY
from test_mock_tcp import running_server


PRIVATE = 'synthetic-private-provider-output'


class CorruptibleProvider(Provider):
    corrupt = False

    def reply(self, payload):
        if self.corrupt and payload['response_format']['json_schema']['name'] == 'agentfit_langextract_candidates':
            self.names.append('agentfit_langextract_candidates')
            return {'malformed': PRIVATE}
        return super().reply(payload)


@contextmanager
def core_flow(provider, *, analysis_mode='integrated-candidates'):
    store = MockStore()
    with service(provider, internal_token='mock-internal', analysis_mode=analysis_mode) as (ai_app, _, processes):
        with running_server(store=store, ai_app=ai_app, analysis_timeout_seconds=45) as (origin, address):
            options = {'base_url': origin, 'trust_env': False, 'timeout': 50,
                       'headers': {'Origin': origin},
                       'cookies': {'better-auth.session_token': 'mock-session-a'}}
            with httpx.Client(**options) as http:
                response = http.post('/api/projects', json={'name': 'Runtime plan'})
                assert response.status_code == 201
                yield http, response.json()['project']['id'], store, processes, options, address


def analyze(http, project_id, document):
    return http.post(f'/api/projects/{project_id}/analysis', content=document.encode(),
                     headers={'Content-Type': 'text/plain'})


def confirm(http, project_id, draft, **changes):
    payload = {'expectedVersion': 0, 'draftId': draft['id'], 'draftVersion': draft['version'],
               'data': dict(draft['data'], **changes)}
    response = http.patch(f'/api/projects/{project_id}/profile', json=payload)
    return response, payload


class CoreFlowRuntimeTests(unittest.TestCase):
    def assert_terminated(self, provider, processes):
        self.assertTrue(provider.closed.wait(3), 'provider socket must close')
        until = time.monotonic() + 3
        while any(p.returncode is None for p in processes) and time.monotonic() < until:
            time.sleep(.01)
        self.assertTrue(processes)
        self.assertTrue(all(p.returncode is not None for p in processes))
        self.assertEqual(provider.errors, [])

    def assert_retry(self, http, p, provider, processes):
        before = len(processes)
        reply = analyze(http, p, provider.document)
        self.assertEqual(reply.status_code, 200)
        check('AnalysisResponse', reply.json())
        self.assertEqual(len(processes), before + 1)
        self.assertEqual(processes[-1].returncode, 0)
        self.assertEqual(provider.errors, [])

    def test_real_analysis_edit_reconnect_duplicate_and_delete(self):
        provider = Provider(missing=True)
        with core_flow(provider) as (http, p, store, processes, options, _):
            analyzed = analyze(http, p, provider.document)
            self.assertEqual(analyzed.status_code, 200)
            check('AnalysisResponse', analyzed.json())
            draft = analyzed.json()['draft']
            self.assertEqual(draft['data'], {
                'project_name': 'TestApp', 'project_type': 'web app', 'domain': 'records',
                'frontend': ['React'], 'backend': ['Go'], 'ai': ['ModelX'], 'database': 'SQLite',
                'deployment': 'CloudZ', 'features': ['기록 저장'], 'external_integrations': ['MailSvc']})
            self.assertEqual(draft['evidence']['frontend'][0]['start'], 24)
            detail = http.get(f'/api/projects/{p}').json()
            self.assertIsNone(detail['confirmed'])
            self.assertEqual(detail['project']['version'], 0)
            self.assertEqual(store._entries[p]['review']['fieldStates']['frontend'], 'unresolved')
            self.assertEqual(provider.names, ['agentfit_langextract_candidates', 'agentfit_operation_candidates',
                'agentfit_candidate_labels', 'agentfit_candidate_label_review', 'agentfit_candidate_source_coverage'])
            saved, payload = confirm(http, p, draft, frontend=['Vue'], ai=[], domain=None)
            self.assertEqual(saved.status_code, 200)
            check('SaveProfileResponse', saved.json())
            confirmed = saved.json()['confirmed']
            self.assertEqual(confirmed['data']['ai'], [])
            self.assertIsNone(confirmed['data']['domain'])
            self.assertEqual(confirmed['sources']['project_name'], 'DOCUMENT')
            self.assertEqual(confirmed['sources']['frontend'], 'USER')
            self.assertEqual(confirmed['sources']['ai'], 'USER')
            self.assertEqual(confirmed['sources']['domain'], 'UNKNOWN')
            self.assertEqual(saved.json()['project']['version'], 1)
            with httpx.Client(**options) as reopened:
                detail = reopened.get(f'/api/projects/{p}').json()
                check('ProjectDetailResponse', detail)
                self.assertEqual(detail['confirmed'], confirmed)
                duplicate = reopened.patch(f'/api/projects/{p}/profile', json=payload)
                self.assertEqual((duplicate.status_code, duplicate.json()['error']['code']), (409, 'VERSION_CONFLICT'))
                self.assertEqual(reopened.get(f'/api/projects/{p}').json(), detail)
                self.assertEqual(reopened.request('DELETE', f'/api/projects/{p}', json={'confirmation': True}).status_code, 204)
                self.assertEqual(reopened.get(f'/api/projects/{p}').status_code, 404)
            self.assertEqual(len(processes), 1)
            self.assertEqual(processes[0].returncode, 0)
            self.assertEqual(provider.errors, [])

    def test_bad_provider_output_preserves_saved_state_and_explicit_retry_recovers(self):
        provider = CorruptibleProvider()
        with core_flow(provider) as (http, p, store, processes, _, __):
            first = analyze(http, p, provider.document)
            self.assertEqual(first.status_code, 200)
            draft = first.json()['draft']
            saved, _ = confirm(http, p, draft)
            self.assertEqual(saved.status_code, 200)
            provider.corrupt = True
            failed = analyze(http, p, provider.document)
            self.assertEqual((failed.status_code, failed.json()['error']['code']), (502, 'AI_UNAVAILABLE'))
            detail = http.get(f'/api/projects/{p}').json()
            self.assertEqual(detail['latestAttempt']['status'], 'FAILED')
            self.assertEqual(detail['draft'], draft)
            self.assertEqual(detail['confirmed'], saved.json()['confirmed'])
            self.assertEqual(detail['project']['version'], 1)
            self.assertEqual(len(processes), 2)  # No automatic retry.
            for sentinel in (PRIVATE, SOLAR_KEY, NVIDIA_KEY):
                self.assertNotIn(sentinel, failed.text + json.dumps(detail) + repr(store.__dict__))
            provider.corrupt = False
            self.assert_retry(http, p, provider, processes)
            self.assertEqual(http.get(f'/api/projects/{p}').json()['confirmed'], saved.json()['confirmed'])

    def test_public_disconnect_stops_real_provider_and_worker_then_releases_admission(self):
        for kind in ('solar', 'nvidia'):
            with self.subTest(provider=kind):
                provider = Provider(hold=kind)
                with core_flow(provider) as (http, p, store, processes, options, address):
                    wire = socket.create_connection(address, timeout=5)
                    try:
                        body = provider.document.encode()
                        head = (f'POST /api/projects/{p}/analysis HTTP/1.1\r\nHost: 127.0.0.1\r\n'
                            f'Origin: {options["base_url"]}\r\nCookie: better-auth.session_token=mock-session-a\r\n'
                            f'Content-Type: text/plain\r\nContent-Length: {len(body)}\r\n\r\n')
                        wire.sendall(head.encode() + body)
                        self.assertTrue(provider.started.wait(12), 'must reach real provider before disconnect')
                        busy = analyze(http, p, provider.document)
                        self.assertEqual((busy.status_code, busy.json()['error']['code']), (409, 'ANALYSIS_BUSY'))
                    finally:
                        wire.close()
                    self.assert_terminated(provider, processes)
                    until = time.monotonic() + 3
                    while store.detail('owner-a', p)['latestAttempt']['status'] == 'PROCESSING' and time.monotonic() < until:
                        time.sleep(.01)
                    detail = http.get(f'/api/projects/{p}').json()
                    self.assertEqual(detail['latestAttempt']['errorCode'], 'INTERRUPTED')
                    self.assertIsNone(detail['draft'])
                    self.assertIsNone(detail['confirmed'])
                    self.assertEqual(len(processes), 1)
                    self.assert_retry(http, p, provider, processes)

    def test_mock_timeout_stops_real_worker_preserves_confirmation_and_allows_retry(self):
        provider = Provider()
        contexts = []
        real_timeout = asyncio.timeout
        def tracked_timeout(seconds):
            context = real_timeout(seconds)
            if seconds == 45:
                contexts.append((asyncio.get_running_loop(), context))
            return context
        with patch('contract_mock.server.asyncio.timeout', tracked_timeout):
            with core_flow(provider) as (http, p, _, processes, __, ___):
                initial = analyze(http, p, provider.document)
                self.assertEqual(initial.status_code, 200)
                draft = initial.json()['draft']
                saved, _ = confirm(http, p, draft)
                self.assertEqual(saved.status_code, 200)
                provider.hold = 'nvidia'
                with ThreadPoolExecutor(max_workers=1) as executor:
                    request = executor.submit(analyze, http, p, provider.document)
                    try:
                        self.assertTrue(provider.started.wait(12), 'must reach real provider before timeout')
                        loop, context = contexts[-1]
                        loop.call_soon_threadsafe(context.reschedule, loop.time())
                        response = request.result(timeout=10)
                    finally:
                        if not request.done():
                            provider.stop.set()
                self.assertEqual((response.status_code, response.json()['error']['code']), (504, 'ANALYSIS_TIMEOUT'))
                self.assert_terminated(provider, processes)
                detail = http.get(f'/api/projects/{p}').json()
                self.assertEqual(detail['latestAttempt']['errorCode'], 'ANALYSIS_TIMEOUT')
                self.assertEqual(detail['draft'], draft)
                self.assertEqual(detail['confirmed'], saved.json()['confirmed'])
                self.assertEqual(len(processes), 2)
                self.assert_retry(http, p, provider, processes)


if __name__ == '__main__':
    unittest.main()
