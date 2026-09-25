"""Validate an AI-produced Project Profile candidate against extracted text."""

from __future__ import annotations

from typing import Any


FIELDS = (
    "project_name",
    "project_type",
    "domain",
    "frontend",
    "backend",
    "ai",
    "database",
    "deployment",
    "features",
    "external_integrations",
)
ARRAY_FIELDS = frozenset(("frontend", "backend", "ai", "features", "external_integrations"))
MAX_TEXT_CODE_POINTS = 200
MAX_ARRAY_ITEMS = 30


class ProfileValidationError(ValueError):
    """A content-free error safe to map to an internal service error code."""

    def __init__(self, code: str, field: str | None = None) -> None:
        self.code = code
        self.field = field
        super().__init__(f"{code}:{field}" if field else code)


def _valid_text(value: Any) -> bool:
    return type(value) is str and bool(value.strip()) and len(value) <= MAX_TEXT_CODE_POINTS


def _validate_value(field: str, value: Any) -> None:
    if value is None:
        return
    if field in ARRAY_FIELDS:
        if type(value) is not list or len(value) > MAX_ARRAY_ITEMS:
            raise ProfileValidationError("INVALID_PROFILE_VALUE", field)
        if not all(_valid_text(item) for item in value):
            raise ProfileValidationError("INVALID_PROFILE_VALUE", field)
    elif not _valid_text(value):
        raise ProfileValidationError("INVALID_PROFILE_VALUE", field)


def validate_profile(document: str, document_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a validated draft candidate with calculated source and unknown fields.

    Literal evidence checks cannot establish semantic certainty. A separate analysis
    stage must handle negation, tentative choices and references to other projects.
    """

    if type(document) is not str or type(document_id) is not str or not document_id:
        raise ProfileValidationError("INVALID_ANALYSIS_INPUT")
    if type(candidate) is not dict or set(candidate) != {"data", "evidence"}:
        raise ProfileValidationError("INVALID_PROFILE_SHAPE")

    data = candidate["data"]
    evidence = candidate["evidence"]
    if type(data) is not dict or set(data) != set(FIELDS):
        raise ProfileValidationError("INVALID_PROFILE_SHAPE")
    if type(evidence) is not dict or set(evidence) != set(FIELDS):
        raise ProfileValidationError("INVALID_EVIDENCE_SHAPE")

    sources: dict[str, str] = {}
    validated_evidence: dict[str, list[dict[str, str | int]]] = {}
    unknown_fields: list[str] = []

    for field in FIELDS:
        value = data[field]
        _validate_value(field, value)

        spans = evidence[field]
        if type(spans) is not list:
            raise ProfileValidationError("INVALID_EVIDENCE_SHAPE", field)
        if value is None:
            if spans:
                raise ProfileValidationError("UNKNOWN_HAS_EVIDENCE", field)
            sources[field] = "UNKNOWN"
            validated_evidence[field] = []
            unknown_fields.append(field)
            continue
        if not spans:
            raise ProfileValidationError("MISSING_EVIDENCE", field)

        checked_spans: list[dict[str, str | int]] = []
        excerpts: list[str] = []
        for span in spans:
            if type(span) is not dict or set(span) != {"start", "end"}:
                raise ProfileValidationError("INVALID_EVIDENCE_SHAPE", field)
            start, end = span["start"], span["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(document):
                raise ProfileValidationError("INVALID_EVIDENCE_RANGE", field)
            excerpts.append(document[start:end])
            checked_spans.append({"documentId": document_id, "start": start, "end": end})

        values = value if field in ARRAY_FIELDS else [value]
        if any(not any(item in excerpt for excerpt in excerpts) for item in values):
            raise ProfileValidationError("EVIDENCE_MISMATCH", field)
        sources[field] = "DOCUMENT"
        validated_evidence[field] = checked_spans

    return {
        "data": {field: data[field] for field in FIELDS},
        "sources": sources,
        "evidence": validated_evidence,
        "unknownFields": unknown_fields,
    }
