"""Actual SDK, request subprocess, HTTP/SSE, and TCP lifecycle with synthetic data."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch

import httpx
import langextract  # Missing optional SDK must fail this dedicated runtime gate.
import uvicorn

from agentfit_ai.analysis_process import run_analysis_process
from agentfit_ai.http_service import create_app
from test_integrated_runtime import DOCUMENT, FACTS, FIELDS, NVIDIA_KEY, SOLAR_KEY, response


HEADERS = {'Authorization': 'Bearer synthetic-internal', 'X-Document-Id': 'DOC',
           'X-Request-Id': 'REQ', 'X-Document-Kind': 'TEXT', 'Content-Type': 'text/plain',
           'X-AgentFit-Analysis-Contract': 'confirmation-v2'}
SHIM = Path(__file__).with_name('integrated_service_fixture.py')


class Provider:
    def __init__(self, *, hold=None, missing=False, many_features=False):
        self.hold, self.missing = hold, missing
        self.started, self.closed, self.stop = (threading.Event() for _ in range(3))
        self.held = False
        self.names, self.errors = [], []
        self.facts = (FACTS[:-1] + [(f'기록 저장 동작 (표현 {i:02})', 'features') for i in range(31)]
                      if many_features else FACTS)
        self.document = '\n'.join(value for value, _ in self.facts)

    def reply(self, payload):
        name = payload['response_format']['json_schema']['name']
        self.names.append(name)
        if name == 'agentfit_langextract_candidates':
            assert self.document in payload['messages'][1]['content']
            return {'extractions': [{'candidate': value, 'candidate_attributes': {'anchor': value}}
                                    for value, _ in self.facts]}
        data = json.loads(payload['messages'][1]['content'])
        if name == 'agentfit_operation_candidates':
            return {'mentions': [{'quote': value, 'anchor': value} for value, field in self.facts if field == 'features']}
        if name == 'agentfit_candidate_labels':
            return {'labels': [{'id': row['id'], 'field': dict(self.facts)[row['value']], 'status': 'confirmed'}
                               for row in data['candidates']]}
        if name == 'agentfit_candidate_label_review':
            return {'checkedCandidateIds': [row['id'] for row in data['selections']],
                    'wrongCandidateIds': [], 'rejectionReasons': []}
        if name == 'agentfit_candidate_source_coverage':
            return {'checkedFields': FIELDS, 'missingFields': ['frontend'] if self.missing else []}
        if name == 'agentfit_feature_grouping':
            ids = [row['id'] for row in data['candidates']]
            return {'groups': [{'representativeId': ids[0], 'memberIds': ids}], 'unrepresentedIds': []}
        if name == 'agentfit_feature_relations':
            return {'assessments': [dict(row, coverage='covered') for row in data['relations']]}
        raise AssertionError('unexpected synthetic provider schema')


@contextmanager
def provider_server(provider):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            kind = self.path.rsplit('/', 1)[-1]
            try:
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                assert kind in ('solar', 'nvidia')
                assert self.headers['Authorization'] == 'Bearer ' + (SOLAR_KEY if kind == 'solar' else NVIDIA_KEY)
                if provider.hold == kind and not provider.held:
                    provider.held = True
                    if kind == 'solar':
                        self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Wait: ')
                    else:
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/event-stream')
                        self.end_headers()
                        self.wfile.write(b': heartbeat\n\n')
                    self.wfile.flush()
                    provider.started.set()
                    until = time.monotonic() + 40
                    while not provider.stop.is_set() and time.monotonic() < until:
                        if select.select([self.connection], [], [], .04)[0]:
                            if self.connection.recv(1, socket.MSG_PEEK) == b'':
                                provider.closed.set()
                                return
                        self.wfile.write(b'x' if kind == 'solar' else b': heartbeat\n\n')
                        self.wfile.flush()
                    return
                body = provider.reply(payload)
                encoded = response(body, payload['model'])
                if kind == 'nvidia':
                    event = {'id': 'synthetic', 'model': payload['model'], 'choices': [{
                        'index': 0, 'delta': {'content': json.dumps(body, ensure_ascii=False)}, 'finish_reason': 'stop'}]}
                    encoded = b'data: ' + json.dumps(event, ensure_ascii=False).encode() + b'\n\ndata: [DONE]\n\n'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json' if kind == 'solar' else 'text/event-stream')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                if provider.started.is_set():
                    provider.closed.set()
            except Exception as error:
                provider.errors.append(type(error).__name__)

        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        provider.stop.set()
        server.shutdown()
        server.server_close()
        thread.join(2)


@contextmanager
def service(provider, *, timeout=30, internal_token='synthetic-internal'):
    processes = []
    original_spawn = asyncio.create_subprocess_exec
    async def capture(*args, **kwargs):
        assert SOLAR_KEY not in str(args) and NVIDIA_KEY not in str(args)
        assert SOLAR_KEY not in str(kwargs['env']) and NVIDIA_KEY not in str(kwargs['env'])
        process = await original_spawn(*args, **kwargs)
        processes.append(process)
        return process
    with provider_server(provider) as endpoint:
        async def worker(*args, **kwargs):
            return await run_analysis_process(*args, **kwargs, command=[sys.executable, str(SHIM), endpoint])
        app = create_app(internal_token=internal_token, analysis_mode='integrated-candidates',
                         max_inflight=1, request_timeout_seconds=timeout)
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=0, access_log=False, log_level='error'))
        thread = threading.Thread(target=server.run, daemon=True)
        with patch.dict(os.environ, {'UPSTAGE_API_KEY': SOLAR_KEY, 'NVIDIA_API_KEY': NVIDIA_KEY,
                                    'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}), patch(
                'agentfit_ai.http_service.run_analysis_process', side_effect=worker), patch(
                'agentfit_ai.analysis_process.asyncio.create_subprocess_exec', side_effect=capture):
            thread.start()
            try:
                until = time.monotonic() + 5
                while not server.started and time.monotonic() < until:
                    time.sleep(.01)
                assert server.started, 'local ASGI server failed to start'
                port = server.servers[0].sockets[0].getsockname()[1]
                yield app, f'http://127.0.0.1:{port}', processes
            finally:
                server.should_exit = True
                thread.join(5)
                assert not thread.is_alive(), 'ASGI server did not stop'


def send(url, document):
    with httpx.Client(trust_env=False, timeout=35) as client:
        return client.post(url + '/internal/v1/analyze', headers=HEADERS, content=document.encode())


class IntegratedServiceRuntimeTests(unittest.TestCase):
    def assert_released(self, provider, processes, url):
        self.assertTrue(provider.closed.wait(3), 'provider socket must close before cleanup')
        until = time.monotonic() + 3
        while processes[0].returncode is None and time.monotonic() < until:
            time.sleep(.01)
        self.assertIsNotNone(processes[0].returncode)
        response = send(url, provider.document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['outcome'], 'needs_confirmation')
        self.assertEqual(len(processes), 2)
        self.assertTrue(all(p.returncode is not None for p in processes))
        self.assertEqual(provider.errors, [])

    def test_actual_sdk_tcp_pipeline_preserves_profile_and_localized_uncertainty(self):
        provider = Provider(missing=True)
        with service(provider) as (_, url, processes):
            output = send(url, provider.document)
            self.assertEqual(output.status_code, 200)
            body = output.json()
            self.assertEqual(body['contract'], 'confirmation-v2')
            self.assertEqual(body['outcome'], 'needs_confirmation')
            self.assertEqual(body['profile']['data'], {
                'project_name': 'TestApp', 'project_type': 'web app', 'domain': 'records',
                'frontend': ['React'], 'backend': ['Go'], 'ai': ['ModelX'], 'database': 'SQLite',
                'deployment': 'CloudZ', 'features': ['기록 저장'], 'external_integrations': ['MailSvc']})
            self.assertEqual(body['profile']['evidence']['frontend'], [{'documentId': 'DOC', 'start': 24, 'end': 29}])
            self.assertEqual(body['fieldStates']['frontend'], 'unresolved')
            self.assertEqual(len(body['questions']), 10)
            self.assertIn({'field': 'frontend', 'questionId': 'confirm_frontend', 'reason': 'REVIEW_ISSUE'}, body['questions'])
            self.assertEqual(provider.names, ['agentfit_langextract_candidates', 'agentfit_operation_candidates',
                'agentfit_candidate_labels', 'agentfit_candidate_label_review', 'agentfit_candidate_source_coverage'])
            self.assertEqual(len(processes), 1)
            self.assertEqual(processes[0].returncode, 0)
            self.assertEqual(provider.errors, [])

    def test_actual_sdk_feature_curation_flows_through_http(self):
        provider = Provider(many_features=True)
        with service(provider) as (_, url, processes):
            output = send(url, provider.document)
            self.assertEqual(output.status_code, 200)
            body = output.json()
            self.assertEqual(body['outcome'], 'needs_confirmation')
            self.assertEqual(body['profile']['data']['features'], ['기록 저장 동작 (표현 00)'])
            self.assertEqual(body['fieldStates']['features'], 'suggested')
            self.assertIn('agentfit_feature_grouping', provider.names)
            self.assertIn('agentfit_feature_relations', provider.names)
            self.assertEqual(processes[0].returncode, 0)
            self.assertEqual(provider.errors, [])

    def test_deadline_during_provider_response_closes_worker_and_releases_slot(self):
        for kind in ('solar', 'nvidia'):
            with self.subTest(provider=kind):
                provider = Provider(hold=kind)
                with service(provider, timeout=10) as (_, url, processes):
                    output = send(url, provider.document)
                    self.assertTrue(provider.started.is_set(), 'must reach actual provider before deadline')
                    self.assertEqual((output.status_code, output.json()), (504, {'error': 'ANALYSIS_DEADLINE_EXCEEDED'}))
                    self.assert_released(provider, processes, url)

    def test_tcp_disconnect_during_provider_response_closes_worker_and_releases_slot(self):
        for kind in ('solar', 'nvidia'):
            with self.subTest(provider=kind):
                provider = Provider(hold=kind)
                with service(provider) as (_, url, processes):
                    port = int(url.rsplit(':', 1)[1])
                    document = provider.document.encode()
                    with socket.create_connection(('127.0.0.1', port), timeout=5) as client:
                        headers = ''.join(f'{k}: {v}\r\n' for k, v in HEADERS.items())
                        client.sendall(('POST /internal/v1/analyze HTTP/1.1\r\nHost: 127.0.0.1\r\n' + headers +
                            f'Content-Length: {len(document)}\r\n\r\n').encode() + document)
                        self.assertTrue(provider.started.wait(12), 'must reach actual provider before disconnect')
                        busy = send(url, provider.document)
                        self.assertEqual((busy.status_code, busy.json()), (503, {'error': 'SERVICE_BUSY'}))
                    self.assert_released(provider, processes, url)

    def test_asgi_cancellation_during_provider_response_closes_worker_and_releases_slot(self):
        for kind in ('solar', 'nvidia'):
            with self.subTest(provider=kind):
                provider = Provider(hold=kind)
                with service(provider) as (app, url, processes):
                    async def cancel_request():
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
                        async def send_message(message):
                            raise AssertionError('cancelled request must not emit response')
                        task = asyncio.create_task(app(scope, receive, send_message))
                        try:
                            self.assertTrue(await asyncio.to_thread(provider.started.wait, 12))
                        finally:
                            task.cancel()
                            with self.assertRaises(asyncio.CancelledError):
                                await task
                    asyncio.run(cancel_request())
                    self.assert_released(provider, processes, url)


if __name__ == '__main__':
    unittest.main()
