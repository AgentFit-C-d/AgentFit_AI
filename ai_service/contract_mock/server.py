"""Local public-contract simulation. Synthetic sessions and in-memory storage only."""
import asyncio
import json
import math

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.requests import ClientDisconnect

from agentfit_ai.http_service import create_app
from .gateway import LocalAnalysisGateway, MEDIA, synthetic_analysis
from .schema import ContractError, check
from .store import MockStore, identifier


async def _body(request, limit):
    declared = request.headers.getlist('content-length')
    if (len(declared) > 1 or declared and (not declared[0].isascii() or not declared[0].isdecimal()
                                         or len(declared[0]) > 20)):
        raise ContractError(400, 'INVALID_INPUT')
    if declared and int(declared[0]) > limit:
        raise ContractError(413, 'INPUT_TOO_LARGE')
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise ContractError(413, 'INPUT_TOO_LARGE')
        data.extend(chunk)
    if declared and len(data) != int(declared[0]):
        raise ContractError(400, 'INVALID_INPUT')
    return bytes(data)


def _media(request):
    values = request.headers.getlist('content-type')
    if len(values) != 1 or request.headers.get('content-encoding'):
        raise ContractError(415, 'UNSUPPORTED_DOCUMENT')
    parts = [v.strip().lower() for v in values[0].split(';')]
    if len(parts) > 2 or len(parts) == 2 and parts[1] not in ('charset=utf-8', 'charset="utf-8"'):
        raise ContractError(415, 'UNSUPPORTED_DOCUMENT')
    return parts[0]


async def _json(request, schema):
    if _media(request) != 'application/json':
        raise ContractError(415, 'UNSUPPORTED_DOCUMENT')
    raw = await _body(request, 65536)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    def invalid(_):
        raise ValueError
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError(400, 'INVALID_INPUT') from None
    check(schema, value)
    return value


def create_mock_app(*, store=None, ai_app=None, sessions=None, origin='http://127.0.0.1:8765',
                    analysis_timeout_seconds=2):
    if (type(analysis_timeout_seconds) not in (int, float) or not math.isfinite(analysis_timeout_seconds)
            or not 0 < analysis_timeout_seconds <= 60):
        raise ValueError('INVALID_MOCK_TIMEOUT')
    store = store or MockStore()
    sessions = dict(sessions if sessions is not None else {'mock-session-a': 'owner-a', 'mock-session-b': 'owner-b'})
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    gateway = LocalAnalysisGateway(ai_app or create_app(internal_token='mock-internal',
        analyze=synthetic_analysis, analysis_mode='integrated-candidates'))
    # Event-loop-owned admission: reserve before awaiting upload, retain through deletion.
    active = {}

    @app.middleware('http')
    async def envelope(request, call_next):
        request.state.request_id = identifier('req')
        try:
            response = await call_next(request)
        except ContractError as error:
            response = JSONResponse(status_code=error.status, content={'error': {
                'code': error.code, 'message': '요청을 처리할 수 없습니다.', 'requestId': request.state.request_id}})
            if error.status == 429:
                response.headers['Retry-After'] = '1'
        except Exception:
            response = JSONResponse(status_code=500, content={'error': {
                'code': 'INTERNAL_ERROR', 'message': '요청을 처리할 수 없습니다.', 'requestId': request.state.request_id}})
        response.headers.update({'Cache-Control': 'no-store', 'X-Request-Id': request.state.request_id,
                                 'X-AgentFit-Mock': 'true'})
        return response

    def owner(request, project_id=None):
        user = sessions.get(request.cookies.get('better-auth.session_token'))
        if user is None:
            raise ContractError(401, 'UNAUTHENTICATED')
        if request.method not in ('GET', 'HEAD') and request.headers.getlist('origin') != [origin]:
            raise ContractError(403, 'FORBIDDEN_ORIGIN')
        if project_id is not None:
            store.detail(user, project_id)
        return user

    @app.post('/api/projects', status_code=201)
    async def create_project(request: Request):
        user = owner(request)
        payload = await _json(request, 'CreateProjectRequest')
        return store.create(user, payload['name'])

    @app.get('/api/projects')
    async def projects(request: Request):
        return store.list(owner(request))

    @app.get('/api/projects/{project_id}')
    async def detail(project_id: str, request: Request):
        return store.detail(owner(request, project_id), project_id)

    @app.patch('/api/projects/{project_id}/profile')
    async def save(project_id: str, request: Request):
        user = owner(request, project_id)
        payload = await _json(request, 'SaveProfileRequest')
        return store.save(user, project_id, payload)

    @app.delete('/api/projects/{project_id}', status_code=204)
    async def delete(project_id: str, request: Request):
        user = owner(request, project_id)
        await _json(request, 'DeleteProjectRequest')
        store.delete(user, project_id)
        return Response(status_code=204)

    @app.post('/api/projects/{project_id}/analysis')
    async def analyze(project_id: str, request: Request):
        user = owner(request, project_id)
        media = _media(request)
        kind = next((k for k, v in MEDIA.items() if v == media), None)
        if kind is None:
            raise ContractError(415, 'UNSUPPORTED_DOCUMENT')
        if project_id in active:
            raise ContractError(409, 'ANALYSIS_BUSY')
        if len(active) >= 2 or user in active.values():
            raise ContractError(429, 'RATE_LIMITED')
        active[project_id] = user
        attempt = None
        def failed(code):
            if attempt:
                try:
                    store.fail(user, project_id, attempt['id'], code)
                except ContractError:
                    pass  # Deleted projects must not be recreated by cleanup.
        try:
            async with asyncio.timeout(analysis_timeout_seconds):
                body = await _body(request, 10485760)
                count = None
                if kind != 'PDF':
                    try:
                        count = len(body.decode('utf-8-sig'))
                    except UnicodeError:
                        raise ContractError(422, 'UNREADABLE_DOCUMENT') from None
                    if count > 100000:
                        raise ContractError(413, 'INPUT_TOO_LARGE')
                attempt = store.begin(user, project_id, {'kind': kind, 'displayName': None,
                    'byteSize': len(body), 'characterCount': count, 'pageCount': None},
                    timeout_seconds=analysis_timeout_seconds)
                result = await gateway.analyze(kind, body, attempt['document']['id'], request.state.request_id)
                return store.finish(user, project_id, attempt['id'], result['profile'], result['review'])
        except TimeoutError:
            failed('ANALYSIS_TIMEOUT')
            raise ContractError(504, 'ANALYSIS_TIMEOUT') from None
        except (asyncio.CancelledError, ClientDisconnect):
            failed('INTERRUPTED')
            raise
        except ContractError as error:
            failed(error.code)
            raise
        except Exception:
            failed('INTERNAL_ERROR')
            raise ContractError(500, 'INTERNAL_ERROR') from None
        finally:
            active.pop(project_id, None)

    return app
