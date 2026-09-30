"""Exercise admission, cancellation and commit boundaries without remote calls."""
import asyncio
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from contract_mock.gateway import synthetic_analysis
from contract_mock.schema import check, ContractError
from contract_mock.server import create_mock_app
from contract_mock.store import MockStore
from test_mock_http import client, DOCUMENT


class ControlledAI:
    def __init__(self):
        self.app = FastAPI()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.cancelled = 0
        self.mode = 'valid'
        @self.app.post('/internal/v1/analyze')
        async def analyze(request: Request):
            self.calls += 1
            text = (await request.body()).decode()
            self.entered.set()
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
            if self.mode == 'exception':
                raise RuntimeError('sensitive-exception-marker')
            value = synthetic_analysis(text, request.headers['x-document-id'])
            value['requestId'] = request.headers['x-request-id']
            if self.mode == 'request-id': value['requestId'] = 'wrong'
            if self.mode == 'evidence': value['profile']['evidence']['frontend'][0]['end'] = 1000
            if self.mode == 'questions': value['questions'][0]['questionId'] = 'tampered'
            return JSONResponse(value)


async def create_project(http):
    response = await http.post('/api/projects', json={'name': 'Plan'})
    return response.json()['project']['id']


async def analyze(http, project_id, content=None):
    return await http.post(f'/api/projects/{project_id}/analysis',
                           content=DOCUMENT.encode() if content is None else content,
                           headers={'Content-Type': 'text/plain'})


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_slots_are_reserved_before_upload_and_returned_after_cancellation(self):
        ai = ControlledAI()
        app = create_mock_app(ai_app=ai.app)
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow_body():
            entered.set()
            await release.wait()
            yield DOCUMENT.encode()
        async with client(app) as http:
            first, second = await create_project(http), await create_project(http)
            task = asyncio.create_task(analyze(http, first, slow_body()))
            try:
                await asyncio.wait_for(entered.wait(), 1)
                duplicate = await analyze(http, first)
                self.assertEqual(duplicate.status_code, 409)
                busy = await analyze(http, second)
                self.assertEqual(busy.status_code, 429)
                self.assertEqual(busy.headers['Retry-After'], '1')
                self.assertEqual(ai.calls, 0)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                release.set()
                ai.release.set()
            self.assertEqual((await analyze(http, first)).status_code, 200)

    async def test_global_limit_and_deleted_inflight_request_keep_physical_slot(self):
        ai = ControlledAI()
        sessions = {'mock-session-a': 'owner-a', 'mock-session-b': 'owner-b', 'mock-session-c': 'owner-c'}
        app = create_mock_app(ai_app=ai.app, sessions=sessions)
        async with client(app) as a, client(app, 'mock-session-b') as b, client(app, 'mock-session-c') as c:
            p, q, r = await create_project(a), await create_project(b), await create_project(c)
            t1 = asyncio.create_task(analyze(a, p))
            await asyncio.wait_for(ai.entered.wait(), 1)
            ai.entered.clear()
            t2 = asyncio.create_task(analyze(b, q))
            try:
                await asyncio.wait_for(ai.entered.wait(), 1)
                self.assertEqual((await analyze(c, r)).status_code, 429)
                deleted = await a.request('DELETE', f'/api/projects/{p}', json={'confirmation': True})
                self.assertEqual(deleted.status_code, 204)
                self.assertEqual((await analyze(c, r)).status_code, 429)
                self.assertEqual(ai.calls, 2)
            finally:
                ai.release.set()
                results = await asyncio.gather(t1, t2)
            self.assertEqual([v.status_code for v in results], [404, 200])
            self.assertEqual((await a.get(f'/api/projects/{p}')).status_code, 404)
            self.assertEqual((await analyze(c, r)).status_code, 200)

    async def test_timeout_cancellation_and_explicit_retry_leave_no_processing_attempt(self):
        for cancelled in (False, True):
            ai = ControlledAI()
            app = create_mock_app(ai_app=ai.app)
            contexts, real_timeout = [], asyncio.timeout
            def tracked_timeout(seconds):
                context = real_timeout(seconds)
                contexts.append(context)
                return context
            with patch('contract_mock.server.asyncio.timeout', tracked_timeout):
                async with client(app) as http:
                    p = await create_project(http)
                    task = asyncio.create_task(analyze(http, p))
                    await asyncio.wait_for(ai.entered.wait(), 1)
                    if cancelled:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                    else:
                        # Expire the real timeout after the request reaches AI; no sleep race.
                        contexts[-1].reschedule(asyncio.get_running_loop().time())
                        response = await task
                        self.assertEqual(response.status_code, 504)
                    detail = (await http.get(f'/api/projects/{p}')).json()
                    self.assertEqual(detail['latestAttempt']['status'], 'FAILED')
                    self.assertEqual(detail['latestAttempt']['errorCode'], 'INTERRUPTED' if cancelled else 'ANALYSIS_TIMEOUT')
                    self.assertEqual(ai.calls, 1)  # No automatic retry.
                    self.assertEqual(ai.cancelled, 1)
                    ai.release.set()
                    self.assertEqual((await analyze(http, p)).status_code, 200)
                    self.assertEqual(ai.calls, 2)

    async def test_invalid_ai_response_never_becomes_a_draft(self):
        for mode in ('request-id', 'questions', 'evidence'):
            with self.subTest(mode=mode):
                ai = ControlledAI(); ai.mode = mode; ai.release.set()
                async with client(create_mock_app(ai_app=ai.app)) as http:
                    p = await create_project(http)
                    response = await analyze(http, p)
                    self.assertEqual(response.status_code, 502)
                    self.assertEqual(response.json()['error']['code'], 'AI_INVALID_OUTPUT')
                    detail = (await http.get(f'/api/projects/{p}')).json()
                    self.assertIsNone(detail['draft'])
                    self.assertEqual(detail['latestAttempt']['status'], 'FAILED')

    async def test_failed_finish_preserves_previous_values_and_releases_slot(self):
        store, ai = MockStore(), ControlledAI()
        ai.release.set()
        app = create_mock_app(store=store, ai_app=ai.app)
        async with client(app) as http:
            p = await create_project(http)
            draft = (await analyze(http, p)).json()['draft']
            payload = {'expectedVersion': 0, 'data': draft['data'], 'draftId': draft['id'], 'draftVersion': 1}
            saved = (await http.patch(f'/api/projects/{p}/profile', json=payload)).json()['confirmed']
            ai.release.clear(); ai.entered.clear()
            task = asyncio.create_task(analyze(http, p))
            await asyncio.wait_for(ai.entered.wait(), 1)
            store.fail_next_write = True
            ai.release.set()
            self.assertEqual((await task).status_code, 503)
            detail = (await http.get(f'/api/projects/{p}')).json()
            self.assertEqual(detail['draft'], draft)
            self.assertEqual(detail['confirmed'], saved)
            self.assertEqual(detail['latestAttempt']['status'], 'FAILED')
            self.assertEqual((await analyze(http, p)).status_code, 200)

    async def test_concurrent_http_confirmations_have_exactly_one_winner(self):
        async with client(create_mock_app()) as http:
            p = await create_project(http)
            data = synthetic_analysis(DOCUMENT, 'doc_x')['profile']['data']
            replies = await asyncio.gather(*(http.patch(f'/api/projects/{p}/profile',
                json={'expectedVersion': 0, 'data': data}) for _ in range(2)))
            self.assertEqual(sorted(r.status_code for r in replies), [200, 409])
            detail = (await http.get(f'/api/projects/{p}')).json()
            check('ProjectDetailResponse', detail)
            self.assertEqual(detail['project']['version'], 1)

    async def test_deadline_matches_config_and_orphan_processing_expires_on_read(self):
        now = [datetime(2026, 9, 30, tzinfo=timezone.utc)]
        store, ai = MockStore(clock=lambda: now[0]), ControlledAI()
        app = create_mock_app(store=store, ai_app=ai.app, analysis_timeout_seconds=.5)
        async with client(app) as http:
            p = await create_project(http)
            task = asyncio.create_task(analyze(http, p))
            try:
                await asyncio.wait_for(ai.entered.wait(), 1)
                attempt = (await http.get(f'/api/projects/{p}')).json()['latestAttempt']
                duration = datetime.fromisoformat(attempt['deadlineAt']) - datetime.fromisoformat(attempt['startedAt'])
                self.assertEqual(duration.total_seconds(), .5)
                now[0] += timedelta(seconds=.5)
                detail = (await http.get(f'/api/projects/{p}')).json()
                self.assertEqual(detail['latestAttempt']['errorCode'], 'INTERRUPTED')
                self.assertEqual(detail['latestAttempt']['status'], 'FAILED')
            finally:
                ai.release.set()
                response = await task
            self.assertEqual(response.status_code, 409)
            self.assertIsNone((await http.get(f'/api/projects/{p}')).json()['draft'])
