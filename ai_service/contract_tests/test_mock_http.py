"""Public mock requests; real document parsing and AI HTTP boundary, fake generation."""
from copy import deepcopy
import json
import unittest

import httpx
from agentfit_ai.http_service import create_app
from contract_mock.gateway import synthetic_analysis
from contract_mock.schema import check
from contract_mock.server import create_mock_app
from contract_mock.store import MockStore
from tests.test_document_extraction import sample_pdf

ORIGIN = 'http://127.0.0.1:8765'
DOCUMENT = 'MockPlan uses React.'


def client(app, token='mock-session-a'):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN,
                             headers={'Origin': ORIGIN}, cookies={'better-auth.session_token': token})


class MockHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_pdf_text_limit_and_worker_timeout_keep_public_error_semantics(self):
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        for internal, status, public in [('DOCUMENT_TEXT_TOO_LONG', 413, 'INPUT_TOO_LARGE'),
                                          ('PDF_TIMEOUT', 504, 'ANALYSIS_TIMEOUT')]:
            with self.subTest(internal=internal):
                ai = FastAPI()
                @ai.post('/internal/v1/analyze')
                async def reject():
                    return JSONResponse({'error': internal}, status_code=422)
                async with client(create_mock_app(ai_app=ai)) as http:
                    p = await self.create_project(http)
                    response = await http.post(f'/api/projects/{p}/analysis', content=b'%PDF-synthetic',
                                               headers={'Content-Type': 'application/pdf'})
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json()['error']['code'], public)

    async def create_project(self, http):
        response = await http.post('/api/projects', json={'name': 'Plan'})
        self.assertEqual(response.status_code, 201)
        check('CreateProjectResponse', response.json())
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-AgentFit-Mock'], 'true')
        self.assertTrue(response.headers['X-Request-Id'])
        return response.json()['project']['id']

    async def test_text_markdown_and_real_pdf_reach_edit_save_and_reconnect(self):
        app = create_mock_app()
        for media, body, kind in [('text/plain', DOCUMENT.encode(), 'TEXT'),
                                  ('text/markdown', DOCUMENT.encode(), 'MARKDOWN'),
                                  ('application/pdf', sample_pdf([DOCUMENT]), 'PDF')]:
            with self.subTest(kind=kind):
                async with client(app) as http:
                    project_id = await self.create_project(http)
                    response = await http.post(f'/api/projects/{project_id}/analysis', content=body,
                                               headers={'Content-Type': media})
                    self.assertEqual(response.status_code, 200, response.text)
                    analysis = response.json(); check('AnalysisResponse', analysis)
                    self.assertEqual(analysis['attempt']['document']['kind'], kind)
                    self.assertEqual(analysis['draft']['kind'], 'DRAFT')
                    self.assertEqual(set(analysis), {'draft', 'attempt'})
                    draft = analysis['draft']
                    edited = deepcopy(draft['data']); edited['frontend'] = ['Vue']; edited['ai'] = []
                    response = await http.patch(f'/api/projects/{project_id}/profile', json={
                        'expectedVersion': 0, 'data': edited, 'draftId': draft['id'], 'draftVersion': draft['version']})
                    self.assertEqual(response.status_code, 200)
                    saved = response.json(); check('SaveProfileResponse', saved)
                    self.assertEqual(saved['confirmed']['sources']['frontend'], 'USER')
                    self.assertEqual(saved['confirmed']['sources']['project_name'], 'DOCUMENT')
                async with client(app) as reconnected:
                    detail = (await reconnected.get(f'/api/projects/{project_id}')).json()
                    check('ProjectDetailResponse', detail)
                    self.assertEqual(detail['confirmed'], saved['confirmed'])
                    self.assertEqual(detail['draft'], draft)
                    self.assertNotIn('draftReview', detail)

    async def test_auth_origin_ownership_and_input_priority(self):
        app = create_mock_app()
        async with client(app) as http, client(app, 'mock-session-b') as other, client(app, 'absent') as anonymous:
            project_id = await self.create_project(http)
            for response, status, code in [
                (await anonymous.post('/api/projects', content=b'bad'), 401, 'UNAUTHENTICATED'),
                (await http.post('/api/projects', json={'name': 'x'}, headers={'Origin': 'https://foreign.invalid'}), 403, 'FORBIDDEN_ORIGIN'),
                (await other.get(f'/api/projects/{project_id}'), 404, 'PROJECT_NOT_FOUND'),
                (await http.get('/api/projects/missing'), 404, 'PROJECT_NOT_FOUND'),
                (await http.post('/api/projects', json={'name': 'x', 'ownerId': 'injected'}), 422, 'INVALID_INPUT'),
                (await http.post('/api/projects', content=b'not-json', headers={'Content-Type': 'application/json'}), 400, 'INVALID_INPUT')]:
                self.assertEqual(response.status_code, status)
                check('ErrorEnvelope', response.json())
                self.assertEqual(response.json()['error']['code'], code)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')

    async def test_oversized_json_and_unsupported_media_fail_before_analysis(self):
        calls = []
        def analyze(*args):
            calls.append(1)
            return synthetic_analysis(*args)
        app = create_mock_app(ai_app=create_app(internal_token='mock-internal', analyze=analyze,
                                               analysis_mode='integrated-candidates'))
        async with client(app) as http:
            project_id = await self.create_project(http)
            response = await http.post('/api/projects', content=b'x' * 65537, headers={'Content-Type': 'application/json'})
            self.assertEqual(response.status_code, 413)
            response = await http.post(f'/api/projects/{project_id}/analysis', content=b'x', headers={'Content-Type': 'application/xml'})
            self.assertEqual(response.status_code, 415)
            response = await http.post(f'/api/projects/{project_id}/analysis', content=b'x' * 10485761,
                                       headers={'Content-Type': 'text/plain'})
            self.assertEqual(response.status_code, 413)
            self.assertEqual(calls, [])

    async def test_invalid_utf8_and_empty_document_are_safe_public_errors(self):
        async with client(create_mock_app()) as http:
            project_id = await self.create_project(http)
            for body, code in [(b'\xff private-marker', 'UNREADABLE_DOCUMENT'), (b'   ', 'EMPTY_DOCUMENT')]:
                response = await http.post(f'/api/projects/{project_id}/analysis', content=body,
                                           headers={'Content-Type': 'text/plain'})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['error']['code'], code)
                self.assertNotIn('private-marker', response.text)

    async def test_v2_nonnull_unresolved_is_saved_as_draft_but_bad_questions_are_rejected(self):
        for malformed in (False, True):
            def analyze(document, document_id):
                outcome = synthetic_analysis(document, document_id)
                outcome['fieldStates']['frontend'] = 'unresolved'
                for question in outcome['questions']:
                    if question['field'] == 'frontend': question['reason'] = 'REVIEW_ISSUE'
                if malformed: outcome['questions'] = []
                return outcome
            app = create_mock_app(ai_app=create_app(internal_token='mock-internal', analyze=analyze,
                                                   analysis_mode='integrated-candidates'))
            async with client(app) as http:
                project_id = await self.create_project(http)
                response = await http.post(f'/api/projects/{project_id}/analysis', content=DOCUMENT.encode(),
                                           headers={'Content-Type': 'text/plain'})
                self.assertEqual(response.status_code, 502 if malformed else 200)
                if not malformed:
                    self.assertEqual(response.json()['draft']['data']['frontend'], ['React'])
                else:
                    self.assertEqual(response.json()['error']['code'], 'AI_INVALID_OUTPUT')
                    self.assertIsNone((await http.get(f'/api/projects/{project_id}')).json()['draft'])

    async def test_ai_200_failed_preserves_previous_draft_and_confirmed(self):
        store, failing = MockStore(), [False]
        def analyze(document, document_id):
            return ({'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_UNAVAILABLE'}
                    if failing[0] else synthetic_analysis(document, document_id))
        app = create_mock_app(store=store, ai_app=create_app(internal_token='mock-internal', analyze=analyze,
                                                           analysis_mode='integrated-candidates'))
        async with client(app) as http:
            project_id = await self.create_project(http)
            original = (await http.post(f'/api/projects/{project_id}/analysis', content=DOCUMENT.encode(),
                                        headers={'Content-Type': 'text/plain'})).json()['draft']
            saved = (await http.patch(f'/api/projects/{project_id}/profile', json={
                'expectedVersion': 0, 'data': original['data'], 'draftId': original['id'], 'draftVersion': 1})).json()['confirmed']
            failing[0] = True
            response = await http.post(f'/api/projects/{project_id}/analysis', content=DOCUMENT.encode(),
                                       headers={'Content-Type': 'text/plain'})
            self.assertEqual(response.status_code, 502)
            detail = (await http.get(f'/api/projects/{project_id}')).json()
            self.assertEqual(detail['draft'], original)
            self.assertEqual(detail['confirmed'], saved)
            self.assertEqual(detail['latestAttempt']['status'], 'FAILED')

    async def test_duplicate_patch_after_lost_response_conflicts_and_get_recovers_commit(self):
        async with client(create_mock_app()) as http:
            project_id = await self.create_project(http)
            payload = {'expectedVersion': 0, 'data': {f: None for f in (
                'project_name', 'project_type', 'domain', 'frontend', 'backend', 'ai',
                'database', 'deployment', 'features', 'external_integrations')}}
            first = await http.patch(f'/api/projects/{project_id}/profile', json=payload)
            self.assertEqual(first.status_code, 200)
            second = await http.patch(f'/api/projects/{project_id}/profile', json=payload)
            self.assertEqual(second.status_code, 409)
            detail = (await http.get(f'/api/projects/{project_id}')).json()
            self.assertEqual(detail['confirmed'], first.json()['confirmed'])
            self.assertEqual(detail['project']['version'], 1)
