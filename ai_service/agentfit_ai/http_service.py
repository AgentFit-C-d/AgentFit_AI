"""AI-side proposal for Spring Boot's private document analysis endpoint."""

import hmac
import os
import re
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from .diagnostics import safe_code
from .document_extraction import (MAX_FILE_BYTES, DocumentExtractionError,
                                  extract_document)
from .profile import FIELDS, ProfileValidationError, validate_profile
from .recoverable_draft import SAFE_REASONS
from .solar import AnalysisError, SolarAnalyzer


IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
MEDIA_TYPES = {"PDF": "application/pdf", "MARKDOWN": "text/markdown",
               "TEXT": "text/plain"}


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


def _solar_analysis(document: str, document_id: str) -> dict:
    key = os.environ.get("UPSTAGE_API_KEY", "")
    if not key:
        raise AnalysisError("MISSING_OR_INVALID_KEY")
    result = SolarAnalyzer(key, analysis_timeout_seconds=40).analyze(document, document_id)
    return {"outcome": "complete", "profile": result.profile}


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
    if set(profile) != {"data", "sources", "evidence", "unknownFields"}:
        raise ProfileValidationError("INVALID_PROFILE_SHAPE")
    evidence = profile["evidence"]
    if type(evidence) is not dict or set(evidence) != set(FIELDS):
        raise ProfileValidationError("INVALID_EVIDENCE_SHAPE")
    spans = {}
    for field in FIELDS:
        items = evidence[field]
        if type(items) is not list:
            raise ProfileValidationError("INVALID_EVIDENCE_SHAPE", field)
        for item in items:
            if (type(item) is not dict or set(item) != {"documentId", "start", "end"}
                    or item["documentId"] != document_id):
                raise ProfileValidationError("INVALID_EVIDENCE_SHAPE", field)
        spans[field] = [{"start": item["start"], "end": item["end"]}
                        for item in items]
    checked = validate_profile(document, document_id,
                               {"data": profile["data"], "evidence": spans})
    if checked != profile:
        raise ProfileValidationError("INVALID_PROFILE_SHAPE")
    return checked


def _checked_confirmation(outcome: dict, profile: dict) -> tuple[dict, list]:
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
        if (field not in FIELDS or field in fields or states[field] != "unresolved" or
                question["reason"] not in SAFE_REASONS | {"ANALYSIS_UNRESOLVED"} or
                question["questionId"] != "confirm_" + field):
            raise ValueError("invalid confirmation question")
        fields.add(field)
    if fields != {field for field in FIELDS if states[field] == "unresolved"}:
        raise ValueError("missing confirmation question")
    return states, questions


def create_app(*, internal_token: str | None = None,
               analyze: Callable[[str, str], dict] | None = None) -> FastAPI:
    """Create a process-local adapter; Spring still owns persistence and public success."""
    token = os.environ.get("AGENTFIT_INTERNAL_TOKEN", "") if internal_token is None else internal_token
    analyze_document = _solar_analysis if analyze is None else analyze
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

        body = bytearray()
        try:
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_FILE_BYTES:
                    return _error(413, "DOCUMENT_TOO_LARGE")
                body.extend(chunk)
            raw = bytes(body)
            if kind == "TEXT":
                try:
                    content = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    return _error(422, "DOCUMENT_INVALID_UTF8")
            else:
                content = raw
            extracted = await run_in_threadpool(extract_document, kind, content)
            outcome = await run_in_threadpool(analyze_document, extracted.text, document_id)
            if type(outcome) is not dict or outcome.get("outcome") not in (
                    "complete", "needs_confirmation", "failed"):
                return _error(500, "INTERNAL_ERROR")
            if outcome["outcome"] == "failed":
                return {"requestId": request_id, "outcome": "failed",
                        "error": safe_code(outcome.get("error"))}
            if type(outcome.get("profile")) is not dict:
                return _error(502, "INVALID_PROFILE_SHAPE")
            profile = _checked_profile(extracted.text, document_id, outcome["profile"])
            if outcome["outcome"] == "complete":
                return {"requestId": request_id, "outcome": "complete",
                        "profile": profile}
            try:
                states, questions = _checked_confirmation(outcome, profile)
            except (TypeError, ValueError):
                return _error(502, "INVALID_ANALYSIS_RESULT")
            return {"requestId": request_id, "outcome": "needs_confirmation",
                    "profile": profile,
                    "fieldStates": states,
                    "questions": questions,
                    "error": safe_code(outcome.get("error"))}
        except DocumentExtractionError as error:
            return _error(422, error.code)
        except AnalysisError as error:
            status = 503 if error.code == "MISSING_OR_INVALID_KEY" else 502
            return _error(status, safe_code(error.code))
        except ProfileValidationError as error:
            return _error(502, safe_code(error.code))
        except Exception:
            return _error(500, "INTERNAL_ERROR")

    return app


app = create_app()
