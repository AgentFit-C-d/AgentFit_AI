"""NVIDIA-only real request worker, SDK, local SSE, and cancellation gates."""

import asyncio
import socket
import time
import unittest

from test_integrated_service import Provider, service, send, HEADERS


class NvidiaServiceRuntimeTests(unittest.TestCase):
    def assert_released(self, provider, processes, url):
        self.assertTrue(provider.closed.wait(3))
        until = time.monotonic() + 3
        while processes[0].returncode is None and time.monotonic() < until:
            time.sleep(.01)
        self.assertIsNotNone(processes[0].returncode)
        output = send(url, provider.document)
        self.assertEqual(output.status_code, 200)
        self.assertEqual(output.json()['contract'], 'confirmation-v2')
        self.assertEqual(len(processes), 2)
        self.assertTrue(all(p.returncode is not None for p in processes))
        self.assertEqual(set(provider.kinds), {'nvidia'})
        self.assertEqual(provider.errors, [])

    def test_actual_nvidia_only_worker_returns_ten_fields_with_review_questions(self):
        provider = Provider(missing=True)
        with service(provider, analysis_mode='integrated-nvidia') as (_, url, processes):
            response = send(url, provider.document)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body['outcome'], 'needs_confirmation')
            self.assertEqual(body['contract'], 'confirmation-v2')
            self.assertEqual(body['profile']['data'], {
                'project_name': 'TestApp', 'project_type': 'web app', 'domain': 'records',
                'frontend': ['React'], 'backend': ['Go'], 'ai': ['ModelX'], 'database': 'SQLite',
                'deployment': 'CloudZ', 'features': ['기록 저장'], 'external_integrations': ['MailSvc']})
            self.assertEqual(body['fieldStates']['frontend'], 'unresolved')
            self.assertEqual(len(body['questions']), 10)
            self.assertEqual(provider.kinds, ['nvidia'] * 5)
            self.assertEqual(len(processes), 1)
            self.assertEqual(processes[0].returncode, 0)
            self.assertEqual(provider.errors, [])

    def test_429_and_503_stop_after_one_call_and_only_explicit_retry_recovers(self):
        for status, code in ((429, 'PROVIDER_RATE_LIMIT'), (503, 'PROVIDER_UNAVAILABLE')):
            with self.subTest(status=status):
                provider = Provider(failure_status=status)
                with service(provider, analysis_mode='integrated-nvidia') as (_, url, processes):
                    response = send(url, provider.document)
                    self.assertEqual((response.status_code, response.json()), (200, {
                        'contract': 'confirmation-v2', 'outcome': 'failed', 'error': code, 'requestId': 'REQ'}))
                    self.assertEqual(provider.kinds, ['nvidia'])
                    self.assertEqual(len(processes), 1)
                    self.assertEqual(processes[0].returncode, 0)
                    provider.failure_status = None
                    recovered = send(url, provider.document)
                    self.assertEqual(recovered.status_code, 200)
                    self.assertEqual(recovered.json()['outcome'], 'needs_confirmation')
                    self.assertEqual(provider.kinds, ['nvidia'] * 6)
                    self.assertEqual(len(processes), 2)
                    self.assertEqual(provider.errors, [])

    def test_absolute_deadline_closes_nvidia_connection_and_request_child(self):
        provider = Provider(hold='nvidia')
        with service(provider, analysis_mode='integrated-nvidia', timeout=10) as (_, url, processes):
            response = send(url, provider.document)
            self.assertTrue(provider.started.is_set())
            self.assertEqual((response.status_code, response.json()),
                             (504, {'error': 'ANALYSIS_DEADLINE_EXCEEDED'}))
            self.assert_released(provider, processes, url)

    def test_public_tcp_disconnect_releases_busy_slot_and_child(self):
        provider = Provider(hold='nvidia')
        with service(provider, analysis_mode='integrated-nvidia') as (_, url, processes):
            document = provider.document.encode()
            port = int(url.rsplit(':', 1)[1])
            with socket.create_connection(('127.0.0.1', port), timeout=5) as client:
                headers = ''.join(f'{k}: {v}\r\n' for k, v in HEADERS.items())
                client.sendall(('POST /internal/v1/analyze HTTP/1.1\r\nHost: 127.0.0.1\r\n' + headers +
                                f'Content-Length: {len(document)}\r\n\r\n').encode() + document)
                self.assertTrue(provider.started.wait(12))
                busy = send(url, provider.document)
                self.assertEqual((busy.status_code, busy.json()), (503, {'error': 'SERVICE_BUSY'}))
            self.assert_released(provider, processes, url)

    def test_asgi_cancellation_reaps_child_before_returning(self):
        provider = Provider(hold='nvidia')
        with service(provider, analysis_mode='integrated-nvidia') as (app, url, processes):
            async def cancel():
                supplied = False
                scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                    'method': 'POST', 'scheme': 'http', 'path': '/internal/v1/analyze',
                    'raw_path': b'/internal/v1/analyze', 'query_string': b'',
                    'headers': [(k.lower().encode(), v.encode()) for k, v in HEADERS.items()]}
                async def receive():
                    nonlocal supplied
                    if not supplied:
                        supplied = True
                        return {'type': 'http.request', 'body': provider.document.encode(), 'more_body': False}
                    await asyncio.Event().wait()
                async def sent(_):
                    raise AssertionError('cancelled request emitted response')
                task = asyncio.create_task(app(scope, receive, sent))
                try:
                    self.assertTrue(await asyncio.to_thread(provider.started.wait, 12))
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
            asyncio.run(cancel())
            self.assert_released(provider, processes, url)


if __name__ == '__main__':
    unittest.main()
