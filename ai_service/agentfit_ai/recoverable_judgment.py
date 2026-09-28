"""Conservatively salvage independently valid fields from a failed judgment."""

from .anchored_candidates import classify
from .profile import FIELDS, validate_profile, ProfileValidationError
from .section_analysis import EXCLUSIONS
from .solar import AnalysisError


_DECISION_KEYS = frozenset({"field", "role", "status", "scope", "decision"})


def salvage_judgment(document: str, document_id: str, pool: list[dict],
                     reply: dict) -> tuple[dict | None, dict[str, str]]:
    """Keep only fields that pass the normal classifier and source validation.

    Unknown candidate IDs or malformed decision objects invalidate the reply as a
    whole. Semantic failures are isolated by field; this never promotes a draft to
    a completed analysis.
    """
    if (type(reply) is not dict or set(reply) != {"decisions"}
            or type(reply["decisions"]) is not dict or type(pool) is not list):
        return None, {}
    decisions = reply["decisions"]
    if (any(type(source) is not dict or type(source.get("id")) is not str
            for source in pool) or len({source["id"] for source in pool}) != len(pool)
            or set(decisions) != {source["id"] for source in pool}):
        return None, {}
    for item in decisions.values():
        if item == {"decision": "irrelevant"}:
            continue
        if (type(item) is not dict or set(item) != _DECISION_KEYS
                or any(type(value) is not str for value in item.values())
                or item["field"] not in FIELDS):
            return None, {}

    data = dict.fromkeys(FIELDS)
    evidence = {field: [] for field in FIELDS}
    unresolved = {}
    for field in FIELDS:
        items = [item for item in decisions.values()
                 if item.get("field") == field]
        if not any(item["decision"] == "selected" for item in items):
            if any(item["decision"] not in EXCLUSIONS for item in items):
                unresolved[field] = "JUDGMENT_INVALID"
            continue
        restricted = {source["id"]: (decisions[source["id"]]
                       if decisions[source["id"]].get("field") == field
                       else {"decision": "irrelevant"}) for source in pool}
        try:
            checked = classify({"decisions": restricted}, pool,
                               document, document_id)
        except AnalysisError:
            unresolved[field] = "JUDGMENT_INVALID"
            continue
        if checked["data"][field] is None:
            unresolved[field] = "JUDGMENT_INVALID"
            continue
        data[field] = checked["data"][field]
        evidence[field] = [{"start": span["start"], "end": span["end"]}
                           for span in checked["evidence"][field]]

    if all(value is None for value in data.values()):
        return None, unresolved
    try:
        profile = validate_profile(document, document_id,
                                   {"data": data, "evidence": evidence})
    except ProfileValidationError:
        return None, {field: "JUDGMENT_INVALID" for field in FIELDS
                      if data[field] is not None or field in unresolved}
    return profile, unresolved
