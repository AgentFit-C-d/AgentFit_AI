"""Project in-memory recoverable analysis suggestions."""

from .diagnostics import safe_code
from .profile import FIELDS, validate_profile


SAFE_REASONS = frozenset({"REVIEW_ISSUE", "JUDGMENT_INVALID",
                          "CANDIDATE_MISSING", "REVIEW_UNAVAILABLE"})


def project_draft(document: str, document_id: str, profile: dict, *,
                  unresolved: dict[str, str], review_complete: bool,
                  error_code: str) -> dict:
    if type(unresolved) is not dict or not set(unresolved) <= set(FIELDS):
        raise ValueError("invalid unresolved fields")
    data = {field: profile["data"][field] for field in FIELDS}
    evidence = {field: [{"start": span["start"], "end": span["end"]}
                        for span in profile["evidence"][field]] for field in FIELDS}
    reasons = dict(unresolved)
    if not review_complete:
        for field in FIELDS:
            if data[field] is None:
                reasons.setdefault(field, "REVIEW_UNAVAILABLE")
    for field in reasons:
        data[field] = None
        evidence[field] = []
    checked = validate_profile(document, document_id,
                               {"data": data, "evidence": evidence})
    states = {field: ("unresolved" if field in reasons else
                      "unknown" if data[field] is None else "suggested")
              for field in FIELDS}
    questions = [{"field": field,
                  "reason": (reasons[field] if reasons[field] in SAFE_REASONS
                             else "ANALYSIS_UNRESOLVED"),
                  "questionId": "confirm_" + field}
                 for field in FIELDS if field in reasons]
    return {"outcome": "needs_confirmation", "profile": checked,
            "fieldStates": states, "questions": questions,
            "error": safe_code(error_code)}
