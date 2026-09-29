"""Resolve model-selected Markdown syntax to exact server-owned source spans."""

import re

from .evidence import EvidenceError, ROLES
from .profile import ARRAY_FIELDS, FIELDS, ProfileValidationError, validate_profile
from .solar import source_lines


CONTRACT_VERSION = "source-selector-v1"
SELECTORS = ("BODY", "AFTER_COLON", "AFTER_EQUALS", "BEFORE_DASH", "AFTER_DASH",
             *(f"CELL_{i}" for i in range(1, 13)),
             *(f"BOLD_{i}" for i in range(1, 9)),
             *(f"CODE_{i}" for i in range(1, 9)))
_PREFIX = re.compile(r"^(?:#{1,6}[ \t]+|>[ \t]*|[-+*][ \t]+|\d{1,9}[.)][ \t]+|\[[ xX]\][ \t]+)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"(?<!`)`([^`\r\n]+)`(?!`)")


def _trim(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _body(text):
    start, end = _trim(text, 0, len(text))
    while True:
        match = _PREFIX.match(text[start:end])
        if not match:
            return start, end
        start, end = _trim(text, start + match.end(), end)


def _line_candidates(text):
    result = {"BODY": _body(text)}
    if "|" in text:
        parts = text.split("|")
        offset = 0
        cell_index = 0
        for part_index, part in enumerate(parts):
            if not ((part_index == 0 and not part.strip())
                    or (part_index == len(parts) - 1 and not part.strip())):
                cell_index += 1
                if cell_index <= 12:
                    result[f"CELL_{cell_index}"] = _trim(text, offset, offset + len(part))
            offset += len(part) + 1
    for prefix, pattern in (("BOLD", _BOLD), ("CODE", _CODE)):
        for index, match in enumerate(pattern.finditer(text), 1):
            if index > 8:
                break
            result[f"{prefix}_{index}"] = match.span(1)
    body_start, body_end = result["BODY"]
    for label, chars in (("AFTER_COLON", ":："), ("AFTER_EQUALS", "="),
                         ("AFTER_DASH", "—")):
        position = next((i for i in range(body_start, body_end) if text[i] in chars), -1)
        if position >= 0:
            rhs_start = position + 1
            if text[rhs_start:rhs_start + 2] == "**":
                rhs_start += 2
            result[label] = _trim(text, rhs_start, body_end)
            if label == "AFTER_DASH":
                result["BEFORE_DASH"] = _trim(text, body_start, position)
    return result


def _resolve(line, selector):
    if type(selector) is not str or selector not in SELECTORS:
        raise EvidenceError("INVALID_SELECTOR")
    span = _line_candidates(line["text"]).get(selector)
    if span is None or span[0] >= span[1]:
        raise EvidenceError("INVALID_SELECTOR")
    start, end = span
    value = line["text"][start:end]
    if not value.strip() or len(value) > 200:
        raise EvidenceError("INVALID_VALUE")
    return value, {"start": line["start"] + start, "end": line["start"] + end}


def source_span(document, line_id, selector):
    if type(document) is not str or type(line_id) is not int:
        raise EvidenceError("INVALID_LINE_ID")
    lines = {line["id"]: line for line in source_lines(document)}
    if line_id not in lines:
        raise EvidenceError("INVALID_LINE_ID")
    return _resolve(lines[line_id], selector)


def _object(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def selector_schema(line_count):
    if type(line_count) is not int or line_count < 1:
        raise ValueError("line_count must be positive")
    line_id = {"type": "integer", "minimum": 1, "maximum": line_count}
    fields = {}
    for field in FIELDS:
        item = _object({"lineId": line_id,
                        "selector": {"type": "string", "enum": list(SELECTORS)},
                        "role": {"type": "string", "enum": list(ROLES[field])}})
        variants = [{"type": "null"}, _object({
            "state": {"type": "string", "enum": ["confirmed"]},
            "items": {"type": "array", "minItems": 1,
                      "maxItems": 30 if field in ARRAY_FIELDS else 1,
                      "items": item}})]
        if field in ARRAY_FIELDS:
            variants.append(_object({"state": {"type": "string", "enum": ["absent"]},
                                     "lineId": line_id}))
        fields[field] = {"anyOf": variants}
    return _object(fields)


def selector_to_profile(document, document_id, fields):
    if type(fields) is not dict or set(fields) != set(FIELDS):
        raise EvidenceError("INVALID_FIELDS")
    lines = {line["id"]: line for line in source_lines(document)}
    data, evidence = {}, {}
    for field in FIELDS:
        data[field], evidence[field] = None, []
        entry = fields[field]
        if entry is None:
            continue
        try:
            if type(entry) is not dict:
                raise EvidenceError("INVALID_STATE")
            if entry.get("state") == "absent":
                if field not in ARRAY_FIELDS or set(entry) != {"state", "lineId"}:
                    raise EvidenceError("INVALID_ABSENCE")
                line_id = entry["lineId"]
                if type(line_id) is not int or line_id not in lines or not lines[line_id]["text"].strip():
                    raise EvidenceError("INVALID_LINE_ID")
                line = lines[line_id]
                data[field] = []
                evidence[field] = [{"start": line["start"], "end": line["end"]}]
                continue
            if set(entry) != {"state", "items"} or entry["state"] != "confirmed":
                raise EvidenceError("INVALID_STATE")
            items = entry["items"]
            limit = 30 if field in ARRAY_FIELDS else 1
            if type(items) is not list or not 1 <= len(items) <= limit:
                raise EvidenceError("INVALID_ITEMS")
            values, spans = [], []
            for index, item in enumerate(items):
                try:
                    if type(item) is not dict or set(item) != {"lineId", "selector", "role"}:
                        raise EvidenceError("INVALID_ITEM")
                    line_id, selector, role = item["lineId"], item["selector"], item["role"]
                    if type(line_id) is not int or line_id not in lines:
                        raise EvidenceError("INVALID_LINE_ID")
                    if type(role) is not str or role not in ROLES[field]:
                        raise EvidenceError("WRONG_ROLE")
                    value, span = _resolve(lines[line_id], selector)
                    if value in values:
                        raise EvidenceError("DUPLICATE_VALUE")
                    values.append(value)
                    spans.append(span)
                except EvidenceError as error:
                    error.index = index
                    raise
            data[field] = values if field in ARRAY_FIELDS else values[0]
            evidence[field] = spans
        except EvidenceError as error:
            error.field = field
            raise
    try:
        return validate_profile(document, document_id, {"data": data, "evidence": evidence})
    except ProfileValidationError as error:
        raise EvidenceError(error.code, error.field) from None
