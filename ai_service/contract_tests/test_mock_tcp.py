"""Actual loopback TCP checks, with non-loopback connects prohibited in this process."""
from contextlib import contextmanager
import socket
from threading import Thread
import time
import unittest
from unittest.mock import patch

import httpx
import uvicorn

from contract_mock.schema import check
from contract_mock.server import create_mock_app
from contract_mock.store import MockStore
from test_mock_analysis_lifecycle import ControlledAI
from test_mock_http import DOCUMENT


@contextmanager
def running_server(**kwargs):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    address = sock.getsockname()
    origin = f'http://127.0.0.1:{address[1]}'
    server = uvicorn.Server(uvicorn.Config(create_mock_app(origin=origin, **kwargs),
        host='127.0.0.1', port=address[1], log_level='critical', access_log=False,
        timeout_graceful_shutdown=3))
    thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    def allowed(target):
        if not isinstance(target, tuple) or target[0] not in ('127.0.0.1', '::1'):
            raise AssertionError('EXTERNAL_CONNECT_PROHIBITED')
    def connect(instance, target):
        allowed(target)
        return original_connect(instance, target)
    def connect_ex(instance, target):
        allowed(target)
        return original_connect_ex(instance, target)
    with patch.object(socket.socket, 'connect', connect), patch.object(socket.socket, 'connect_ex', connect_ex):
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.01)
            if not server.started:
                raise AssertionError('MOCK_START_FAILED')
            yield origin, address
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            sock.close()
            if thread.is_alive():
                raise AssertionError('MOCK_SERVER_NOT_STOPPED')


class TcpTests(unittest.TestCase):
    def test_create_analyze_edit_reconnect_delete_over_real_loopback(self):
        with running_server() as (origin, _):
            options = {'base_url': origin, 'trust_env': False, 'headers': {'Origin': origin},
                       'cookies': {'better-auth.session_token': 'mock-session-a'}, 'timeout': 5}
            with httpx.Client(**options) as http:
                created = http.post('/api/projects', json={'name': 'TCP plan'})
                self.assertEqual(created.status_code, 201)
                p = created.json()['project']['id']
                response = http.post(f'/api/projects/{p}/analysis', content=DOCUMENT,
                                     headers={'Content-Type': 'text/plain'})
                self.assertEqual(response.status_code, 200)
                check('AnalysisResponse', response.json())
                draft = response.json()['draft']
                data = dict(draft['data'], frontend=['Vue'])
                response = http.patch(f'/api/projects/{p}/profile', json={'expectedVersion': 0,
                    'data': data, 'draftId': draft['id'], 'draftVersion': draft['version']})
                self.assertEqual(response.status_code, 200)
                saved = response.json()['confirmed']
            with httpx.Client(**options) as reopened:
                detail = reopened.get(f'/api/projects/{p}').json()
                self.assertEqual(detail['confirmed'], saved)
                self.assertEqual(detail['confirmed']['sources']['frontend'], 'USER')
                deleted = reopened.request('DELETE', f'/api/projects/{p}', json={'confirmation': True})
                self.assertEqual(deleted.status_code, 204)
                self.assertEqual(deleted.content, b'')
                self.assertEqual(reopened.get(f'/api/projects/{p}').status_code, 404)
                self.assertEqual(reopened.get('/api/projects').json(), {'projects': []})

    def test_tcp_disconnect_cleans_attempt_before_timeout(self):
        store, ai = MockStore(), ControlledAI()
        p = store.create('owner-a', 'Disconnect')['project']['id']
        with running_server(store=store, ai_app=ai.app) as (origin, address):
            wire = socket.create_connection(address, timeout=2)
            try:
                body = DOCUMENT.encode()
                headers = (f'POST /api/projects/{p}/analysis HTTP/1.1\r\nHost: {address[0]}:{address[1]}\r\n'
                    f'Origin: {origin}\r\nCookie: better-auth.session_token=mock-session-a\r\n'
                    f'Content-Type: text/plain\r\nContent-Length: {len(body)}\r\n\r\n').encode()
                wire.sendall(headers + body)
                deadline = time.monotonic() + 1
                while store.detail('owner-a', p)['latestAttempt'] is None and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertEqual(store.detail('owner-a', p)['latestAttempt']['status'], 'PROCESSING')
            finally:
                wire.close()
            deadline = time.monotonic() + .5
            while store.detail('owner-a', p)['latestAttempt']['status'] == 'PROCESSING' and time.monotonic() < deadline:
                time.sleep(.01)
            detail = store.detail('owner-a', p)
            self.assertEqual(detail['latestAttempt']['errorCode'], 'INTERRUPTED')
            self.assertIsNone(detail['draft'])


class ResponseLossTests(unittest.IsolatedAsyncioTestCase):
    async def test_committed_patch_is_recovered_after_transport_loses_response(self):
        inner = create_mock_app()
        async def lossy(scope, receive, send):
            async def forward(message):
                if scope['method'] == 'PATCH' and message['type'] == 'http.response.start':
                    raise httpx.ReadError('SYNTHETIC_RESPONSE_LOSS')
                await send(message)
            await inner(scope, receive, forward)
        from test_mock_http import client
        async with client(lossy) as http:
            p = (await http.post('/api/projects', json={'name': 'Loss'})).json()['project']['id']
            data = {f: None for f in ('project_name', 'project_type', 'domain', 'database', 'deployment',
                                      'frontend', 'backend', 'ai', 'features', 'external_integrations')}
            data['project_name'] = 'Saved before response loss'
            with self.assertRaises(httpx.ReadError):
                await http.patch(f'/api/projects/{p}/profile', json={'expectedVersion': 0, 'data': data})
            detail = (await http.get(f'/api/projects/{p}')).json()
            self.assertEqual(detail['project']['version'], 1)
            self.assertEqual(detail['confirmed']['data']['project_name'], 'Saved before response loss')
