"""AI-side proposal for Spring Boot's private document analysis endpoint."""

import asyncio
import hmac
import os
import re
from collections.abc import Callable
from threading import BoundedSemaphore

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from .analysis_process import AnalysisProcessError, run_analysis_process
from .candidate_confirmation import CONTRACT, validate_candidate_confirmation
from .diagnostics import safe_code
from .document_extraction import (MAX_FILE_BYTES, PDF_TIMEOUT_SECONDS,
                                  DocumentExtractionError,
                                  extract_document)
from .profile import FIELDS, ProfileValidationError, check_profile_snapshot
from .recoverable_draft import SUGGESTED_REASONS, UNRESOLVED_REASONS
from .solar import AnalysisError


IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
MEDIA_TYPES = {"PDF": "application/pdf", "MARKDOWN": "text/markdown",
               "TEXT": "text/plain"}
_DISCONNECTED = object()
_CONFIGURATION_ERRORS = frozenset(('MISSING_OR_INVALID_KEY', 'INTEGRATED_RUNTIME_UNAVAILABLE'))


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


class _AdmittedResponse(JSONResponse):
    """Release an analysis slot after the ASGI response finishes or aborts."""

    def __init__(self, *, release, **kwargs):
        super().__init__(**kwargs)
        self._release = release

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._release()


class _AbortedResponse(Response):
    """Finish a disconnected request without sending onto its closed socket."""

    def __init__(self, release):
        super().__init__(status_code=204)
        self._release = release

    async def __call__(self, scope, receive, send):
        self._release()


async def _wait_for_disconnect(request: Request) -> None:
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return
        await asyncio.sleep(.05)


async def _run_default_analysis(request: Request, document: str, document_id: str,
                                deadline: float, *, recoverable_solar: bool = False,
                                integrated_candidates: bool = False) -> dict:
    key = os.environ.get("UPSTAGE_API_KEY", "")
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "") if integrated_candidates else None
    if not key.strip() or (integrated_candidates and not nvidia_key.strip()):
        raise AnalysisError("MISSING_OR_INVALID_KEY")
    if await request.is_disconnected():
        return _DISCONNECTED
    if integrated_candidates:
        worker = asyncio.create_task(run_analysis_process(
            document, document_id, key, deadline, integrated_candidates=True, nvidia_key=nvidia_key))
    elif recoverable_solar:
        worker = asyncio.create_task(run_analysis_process(
            document, document_id, key, deadline, recoverable_solar=True))
    else:
        worker = asyncio.create_task(run_analysis_process(document, document_id, key, deadline))
    disconnect = asyncio.create_task(_wait_for_disconnect(request))
    try:
        async with asyncio.timeout_at(deadline):
            done, _ = await asyncio.wait({worker, disconnect},
                                         return_when=asyncio.FIRST_COMPLETED)
            if disconnect in done:
                return _DISCONNECTED
            return await worker
    finally:
        if not worker.done():
            worker.cancel()
        if not disconnect.done():
            disconnect.cancel()
        await asyncio.gather(worker, disconnect, return_exceptions=True)


def _media_type_valid(value: str | None, kind: str) -> bool:
    if value is None:
        return False
    parts = [part.strip().lower() for part in value.split(";")]
    if parts[0] != MEDIA_TYPES[kind]:
        return False
    if kind == "PDF":
        return len(parts) == 1
    return len(parts) == 1 or (len(parts) == 2 and parts[1] == "charset=utf-8")


def _checked_profile(document: str, document_id: str, profile: dict) -> dict:
    return check_profile_snapshot(document, document_id, profile)


def _checked_confirmation(outcome: dict, profile: dict, *,
                          require_suggested_questions: bool = False) -> tuple[dict, list]:
    states = outcome.get("fieldStates")
    questions = outcome.get("questions")
    if (type(states) is not dict or set(states) != set(FIELDS) or
            any(state not in ("suggested", "unknown", "unresolved")
                for state in states.values()) or
            type(questions) is not list or len(questions) > len(FIELDS)):
        raise ValueError("invalid confirmation result")
    if any((profile["data"][field] is None) != (states[field] != "suggested")
           for field in FIELDS):
        raise ValueError("confirmation state contradicts profile")
    fields = set()
    for question in questions:
        if type(question) is not dict or set(question) != {"field", "reason", "questionId"}:
            raise ValueError("invalid confirmation question")
        field = question["field"]
        if field not in FIELDS or field in fields:
            raise ValueError("invalid confirmation question")
        valid_reason = (
            (states[field] == "unresolved" and
             question["reason"] in UNRESOLVED_REASONS | {"ANALYSIS_UNRESOLVED"}) or
            (states[field] == "suggested" and
             question["reason"] in SUGGESTED_REASONS))
        if not valid_reason or question["questionId"] != "confirm_" + field:
            raise ValueError("invalid confirmation question")
        fields.add(field)
    if not {field for field in FIELDS if states[field] == "unresolved"} <= fields:
        raise ValueError("missing confirmation question")
    if (require_suggested_questions and
            not {field for field in FIELDS if states[field] == "suggested"} <= fields):
        raise ValueError("missing suggested confirmation question")
    return states, questions


def _bounded_setting(value: int | None, name: str, default: int, maximum: int) -> int:
    if value is None:
        raw = os.environ.get(name, str(default))
        if not raw.isascii() or not raw.isdecimal() or len(raw) > len(str(maximum)):
            raise ValueError("invalid service setting: " + name)
        value = int(raw)
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("invalid service setting: " + name)
    return value


def create_app(*, internal_token: str | None = None,
               analyze: Callable[[str, str], dict] | None = None,
               analysis_mode: str | None = None,
               max_inflight: int | None = None,
               upload_timeout_seconds: int | None = None,
               request_timeout_seconds: int | None = None) -> FastAPI:
    """Create a process-local adapter; Spring still owns persistence and public success."""
    token = os.environ.get("AGENTFIT_INTERNAL_TOKEN", "") if internal_token is None else internal_token
    mode = (os.environ.get("AGENTFIT_ANALYSIS_MODE", "default")
            if analysis_mode is None else analysis_mode)
    if mode not in ("default", "recoverable-solar", "integrated-candidates"):
        raise ValueError("invalid analysis mode")
    limit = _bounded_setting(max_inflight, "AGENTFIT_MAX_INFLIGHT_ANALYSES", 2, 8)
    upload_timeout = _bounded_setting(upload_timeout_seconds,
                                      "AGENTFIT_UPLOAD_TIMEOUT_SECONDS", 10, 30)
    request_timeout = _bounded_setting(request_timeout_seconds,
                                       "AGENTFIT_REQUEST_TIMEOUT_SECONDS",
                                       1800 if mode == 'integrated-candidates' else 60,
                                       3600 if mode == 'integrated-candidates' else 120)
    slots = BoundedSemaphore(limit)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    async def health() -> dict:
        return {"status": "alive"}

    @app.post("/internal/v1/analyze")
    async def analyze_request(request: Request):
        if not token:
            return _error(503, "SERVICE_NOT_CONFIGURED")
        if len(request.headers.getlist("authorization")) != 1:
            return _error(401, "UNAUTHORIZED")
        authorization = request.headers.get("authorization", "")
        supplied = authorization.removeprefix("Bearer ")
        if not authorization.startswith("Bearer ") or not hmac.compare_digest(supplied, token):
            return _error(401, "UNAUTHORIZED")
        if (mode in ("recoverable-solar", "integrated-candidates") and
                request.headers.getlist("x-agentfit-analysis-contract") !=
                [CONTRACT if mode == 'integrated-candidates' else "confirmation-v1"]):
            return _error(428, "CONFIRMATION_CONTRACT_REQUIRED")

        document_id = request.headers.get("x-document-id", "")
        request_id = request.headers.get("x-request-id", "")
        if len(request.headers.getlist("x-document-id")) != 1:
            return _error(400, "INVALID_DOCUMENT_ID")
        if len(request.headers.getlist("x-request-id")) != 1:
            return _error(400, "INVALID_REQUEST_ID")
        if not IDENTIFIER.fullmatch(document_id):
            return _error(400, "INVALID_DOCUMENT_ID")
        if not IDENTIFIER.fullmatch(request_id):
            return _error(400, "INVALID_REQUEST_ID")
        kind = request.headers.get("x-document-kind", "")
        if len(request.headers.getlist("x-document-kind")) != 1:
            return _error(400, "INVALID_DOCUMENT_KIND")
        if kind not in MEDIA_TYPES:
            return _error(400, "INVALID_DOCUMENT_KIND")
        if len(request.headers.getlist("content-type")) != 1:
            return _error(415, "UNSUPPORTED_MEDIA_TYPE")
        if not _media_type_valid(request.headers.get("content-type"), kind):
            return _error(415, "UNSUPPORTED_MEDIA_TYPE")
        if request.headers.get("content-encoding"):
            return _error(415, "UNSUPPORTED_CONTENT_ENCODING")
        declared = request.headers.get("content-length")
        if len(request.headers.getlist("content-length")) > 1:
            return _error(400, "INVALID_CONTENT_LENGTH")
        if declared is not None:
            if len(declared) > 20 or not declared.isascii() or not declared.isdecimal():
                return _error(400, "INVALID_CONTENT_LENGTH")
            if int(declared) > MAX_FILE_BYTES:
                return _error(413, "DOCUMENT_TOO_LARGE")

        if not slots.acquire(blocking=False):
            return JSONResponse(status_code=503, content={"error": "SERVICE_BUSY"},
                                headers={"Retry-After": "1"})

        release_here = True
        deadline = asyncio.get_running_loop().time() + request_timeout

        def finish(status: int, content: dict) -> _AdmittedResponse:
            nonlocal release_here
            response = _AdmittedResponse(status_code=status, content=content,
                                         release=slots.release)
            release_here = False
            return response

        def fail(status: int, code: str) -> _AdmittedResponse:
            return finish(status, {"error": code})

        body = bytearray()
        try:
            try:
                async with asyncio.timeout_at(min(
                        deadline, asyncio.get_running_loop().time() + upload_timeout)):
                    async for chunk in request.stream():
                        if len(body) + len(chunk) > MAX_FILE_BYTES:
                            return fail(413, "DOCUMENT_TOO_LARGE")
                        body.extend(chunk)
            except TimeoutError:
                if asyncio.get_running_loop().time() >= deadline:
                    return fail(504, "ANALYSIS_DEADLINE_EXCEEDED")
                return fail(408, "DOCUMENT_UPLOAD_TIMEOUT")
            raw = bytes(body)
            if kind == "TEXT":
                try:
                    content = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    return fail(422, "DOCUMENT_INVALID_UTF8")
            else:
                content = raw
            if (kind == "PDF" and asyncio.get_running_loop().time() +
                    PDF_TIMEOUT_SECONDS + 1 >= deadline):
                return fail(504, "ANALYSIS_DEADLINE_EXCEEDED")
            async with asyncio.timeout_at(deadline):
                extracted = await run_in_threadpool(extract_document, kind, content)
            if analyze is None:
                outcome = await _run_default_analysis(
                    request, extracted.text, document_id, deadline,
                    recoverable_solar=(mode == "recoverable-solar"),
                    integrated_candidates=(mode == 'integrated-candidates'))
                if outcome is _DISCONNECTED:
                    response = _AbortedResponse(slots.release)
                    release_here = False
                    return response
            else:
                async with asyncio.timeout_at(deadline):
                    outcome = await run_in_threadpool(analyze, extracted.text, document_id)
            if type(outcome) is dict and set(outcome) == {"error"}:
                code = safe_code(outcome["error"])
                return fail(503 if code in _CONFIGURATION_ERRORS else 502, code)
            if mode == 'integrated-candidates':
                if (type(outcome) is dict and set(outcome) == {'contract', 'outcome', 'error'}
                        and outcome['contract'] == CONTRACT and outcome['outcome'] == 'failed'
                        and type(outcome['error']) is str and safe_code(outcome['error']) == outcome['error']):
                    return finish(200, dict(outcome, requestId=request_id))
                try:
                    checked = validate_candidate_confirmation(extracted.text, document_id, outcome)
                except (TypeError, ValueError, KeyError):
                    return fail(502, 'INVALID_ANALYSIS_RESULT')
                return finish(200, dict(checked, requestId=request_id))
            if type(outcome) is dict and 'contract' in outcome:
                return fail(502, 'INVALID_ANALYSIS_RESULT')
            if type(outcome) is not dict or outcome.get("outcome") not in (
                    "complete", "needs_confirmation", "failed"):
                return fail(500, "INTERNAL_ERROR")
            if outcome["outcome"] == "failed":
                return finish(200, {"requestId": request_id, "outcome": "failed",
                                    "error": safe_code(outcome.get("error"))})
            if type(outcome.get("profile")) is not dict:
                return fail(502, "INVALID_PROFILE_SHAPE")
            profile = _checked_profile(extracted.text, document_id, outcome["profile"])
            if outcome["outcome"] == "complete":
                return finish(200, {"requestId": request_id, "outcome": "complete",
                                    "profile": profile})
            try:
                states, questions = _checked_confirmation(
                    outcome, profile,
                    require_suggested_questions=(mode == "recoverable-solar"))
            except (TypeError, ValueError):
                return fail(502, "INVALID_ANALYSIS_RESULT")
            return finish(200, {"requestId": request_id, "outcome": "needs_confirmation",
                                "profile": profile,
                                "fieldStates": states,
                                "questions": questions,
                                "error": safe_code(outcome.get("error"))})
        except DocumentExtractionError as error:
            return fail(422, error.code)
        except AnalysisError as error:
            status = 503 if error.code in _CONFIGURATION_ERRORS else 502
            return fail(status, safe_code(error.code))
        except AnalysisProcessError as error:
            status = 504 if error.code == "ANALYSIS_DEADLINE_EXCEEDED" else 502
            return fail(status, error.code)
        except TimeoutError:
            return fail(504, "ANALYSIS_DEADLINE_EXCEEDED")
        except ProfileValidationError as error:
            return fail(502, safe_code(error.code))
        except Exception:
            return fail(500, "INTERNAL_ERROR")
        finally:
            if release_here:
                slots.release()

    return app


app = create_app()
