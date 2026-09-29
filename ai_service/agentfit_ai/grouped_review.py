"""Strict field-scoped semantic review for opt-in source selector analysis."""

from copy import deepcopy

from .compact_review import item_ids, normalize_compact_review, review_payload
from .profile import FIELDS
from .semantic_review import ReviewValidationError


GROUPS = (
    ("project_name", "project_type", "domain", "frontend", "backend"),
    ("ai", "database", "deployment", "external_integrations"),
    ("features",),
)

FIELDWISE_GROUPS = (GROUPS[0], ("ai",), ("database",),
                    ("deployment",), ("external_integrations",), GROUPS[2])


def _valid_fields(fields):
    return (type(fields) is tuple and fields in (*GROUPS, *FIELDWISE_GROUPS) and
            len(fields) == len(set(fields)) and set(fields) <= set(FIELDS))


def group_review_payload(document, profile, fields, *, model, effort,
                         max_tokens=4096):
    if not _valid_fields(fields):
        raise ValueError("unsupported review group")
    if type(max_tokens) is not int or max_tokens not in (4096, 8192):
        raise ValueError("unsupported group review output limit")
    payload = review_payload(document, profile, model=model, effort=effort,
                             fields=fields)
    payload["max_tokens"] = max_tokens
    prompt = payload["messages"][0]["content"]
    prompt = prompt.replace("10개 필드를 모두 검토한다", "지정된 필드만 검토한다")
    prompt = "\n".join(
        line for line in prompt.splitlines() if not line.startswith("출력은 "))
    payload["messages"][0]["content"] = prompt + (
        "\n이번 호출에서는 다음 필드만 독립적으로 검토한다: " + ", ".join(fields) +
        '. 다른 필드의 이슈는 반환하지 않는다. 출력은 {"checkedFields":[지정 필드 전체],'
        '"issues":[오류 항목]} 형식이다. checkedFields에 지정 필드를 각각 한 번 적는다.'
    )
    schema = payload["response_format"]["json_schema"]
    schema["name"] = "agentfit_grouped_review"
    props = schema["schema"]["properties"]
    issue_props = props["issues"]["items"]["properties"]
    ids_by_field = item_ids(profile)
    variants = []
    for field in fields:
        variant_props = deepcopy(issue_props)
        variant_props["field"] = {"type": "string", "enum": [field]}
        ids = ids_by_field.get(field, [])
        variant_props["targetId"] = ({"anyOf": [
            {"type": "null"}, {"type": "string", "enum": ids}]}
            if ids else {"type": "null"})
        variants.append({"type": "object", "properties": variant_props,
                         "required": list(variant_props), "additionalProperties": False})
    props["issues"]["items"] = {"anyOf": variants}
    props["checkedFields"] = {
        "type": "array", "minItems": len(fields), "maxItems": len(fields),
        "items": {"type": "string", "enum": list(fields)},
    }
    schema["schema"]["required"] = ["checkedFields", "issues"]
    return payload


def normalize_group_review(reply, profile, document, fields):
    if not _valid_fields(fields):
        raise ReviewValidationError("CHECKED_FIELDS")
    if type(reply) is not dict or set(reply) != {"checkedFields", "issues"}:
        raise ReviewValidationError("ROOT_SHAPE")
    checked = reply["checkedFields"]
    if (type(checked) is not list or len(checked) != len(fields) or
            any(type(item) is not str for item in checked) or
            set(checked) != set(fields)):
        raise ReviewValidationError("CHECKED_FIELDS")
    issues = reply["issues"]
    if type(issues) is not list or any(type(issue) is not dict or
                                       issue.get("field") not in fields for issue in issues):
        raise ReviewValidationError("ISSUE_ENUM")
    normalized = normalize_compact_review({"issues": issues}, profile, document)
    return {"checkedFields": list(fields), "issues": normalized}
