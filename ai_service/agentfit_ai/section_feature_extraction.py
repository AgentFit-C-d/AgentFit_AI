"""Source-selector feature extraction scoped to complete source ranges."""

from copy import deepcopy

from .evidence import EvidenceError, ROLES
from .section_feature_review import _heading_context, validate_section_coverage
from .solar import FREQUENCY_PENALTY, REASONING_EFFORT, source_lines
from .source_selector import selector_schema, source_span


def _check_chunk(lines, chunk):
    if (type(chunk) is not tuple or len(chunk) != 2 or
            any(type(number) is not int for number in chunk) or
            not 1 <= chunk[0] <= chunk[1] <= len(lines) or
            chunk[1] - chunk[0] + 1 > 120):
        raise EvidenceError("SECTION_RANGE_INVALID", "features")


def section_extraction_payload(document, chunk, *, model):
    from .source_selector_analysis import EXTRACTION_PROMPT

    lines = source_lines(document)
    _check_chunk(lines, chunk)
    feature = deepcopy(selector_schema(len(lines))["properties"]["features"])
    confirmed = feature["anyOf"][1]
    absent = feature["anyOf"][2]
    local_line = {"type": "integer", "minimum": chunk[0], "maximum": chunk[1]}
    confirmed["properties"]["items"]["items"]["properties"]["lineId"] = local_line
    absent["properties"]["lineId"] = local_line
    schema = {"type": "object", "properties": {"features": feature},
              "required": ["features"], "additionalProperties": False}
    context = _heading_context(lines, chunk[0])
    content = "Context headings (read-only; not valid evidence):\n"
    content += "\n".join(f"[L{line['id']}] {line['text']}" for line in context)
    content += "\nSource lines to extract:\n"
    content += "\n".join(f"[L{line['id']}] {line['text']}"
                         for line in lines[chunk[0] - 1:chunk[1]])
    prompt = (EXTRACTION_PROMPT +
              "\n이번 호출에서는 features 필드만 반환한다. 이 구역 안의 확정된 사용자·운영 동작만 "
              "선택하고 다른 구역은 알 수 없으므로 누락을 보충하려고 추측하지 않는다. "
              "문맥용 제목은 선택할 수 없다. 모든 lineId는 이 구역 안이어야 한다. "
              "이 구역에 기능이 없으면 null이다. 문서 전체에서 기능이 없다고 명시 확정한 "
              "경우에만 absent를 쓴다.")
    return {"model": model,
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": content}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "agentfit_section_feature_extraction", "strict": True,
                "schema": schema}},
            "reasoning_effort": REASONING_EFFORT,
            "frequency_penalty": FREQUENCY_PENALTY, "temperature": 0,
            "max_tokens": 4096, "stream": False}


def normalize_section_features(document, chunk, reply):
    lines = source_lines(document)
    _check_chunk(lines, chunk)
    if type(reply) is not dict or set(reply) != {"features"}:
        raise EvidenceError("INVALID_FIELDS", "features")
    entry = reply["features"]
    if entry is None:
        return None
    if type(entry) is not dict:
        raise EvidenceError("INVALID_STATE", "features")
    if entry.get("state") == "absent":
        if set(entry) != {"state", "lineId"}:
            raise EvidenceError("INVALID_ABSENCE", "features")
        ref = entry["lineId"]
        if type(ref) is not int or not chunk[0] <= ref <= chunk[1] or not lines[ref - 1]["text"].strip():
            raise EvidenceError("SECTION_SOURCE_LINE_INVALID", "features")
        return entry
    if set(entry) != {"state", "items"} or entry["state"] != "confirmed":
        raise EvidenceError("INVALID_STATE", "features")
    items = entry["items"]
    if type(items) is not list or not 1 <= len(items) <= 30:
        raise EvidenceError("INVALID_ITEMS", "features")
    seen_values = set()
    for index, item in enumerate(items):
        if type(item) is not dict or set(item) != {"lineId", "selector", "role"}:
            raise EvidenceError("INVALID_ITEM", "features", index)
        ref = item["lineId"]
        if type(ref) is not int or not chunk[0] <= ref <= chunk[1]:
            raise EvidenceError("SECTION_SOURCE_LINE_INVALID", "features", index)
        if type(item["role"]) is not str or item["role"] not in ROLES["features"]:
            raise EvidenceError("WRONG_ROLE", "features", index)
        try:
            value, _ = source_span(document, ref, item["selector"])
        except EvidenceError as error:
            raise EvidenceError(error.reason, "features", index) from None
        if value in seen_values:
            raise EvidenceError("DUPLICATE_VALUE", "features", index)
        seen_values.add(value)
    return entry


def merge_section_features(document, chunks, replies):
    if len(chunks) != len(replies):
        raise EvidenceError("SECTION_COVERAGE_INVALID", "features")
    try:
        validate_section_coverage(chunks, len(source_lines(document)))
    except ValueError:
        raise EvidenceError("SECTION_COVERAGE_INVALID", "features") from None
    entries = [normalize_section_features(document, chunk, reply)
               for chunk, reply in zip(chunks, replies)]
    sourced_items = []
    absence = None
    for entry in entries:
        if entry is None:
            continue
        if entry["state"] == "absent":
            if absence is None:
                absence = entry
            continue
        for item in entry["items"]:
            value, span = source_span(document, item["lineId"], item["selector"])
            sourced_items.append((span["start"], value, item))
    if absence is not None and sourced_items:
        raise EvidenceError("SECTION_FEATURE_CONFLICT", "features")
    chosen = []
    seen_values = set()
    for _, value, item in sorted(sourced_items, key=lambda entry: entry[0]):
        if value not in seen_values:
            chosen.append(item)
            seen_values.add(value)
            if len(chosen) > 30:
                raise EvidenceError("SECTION_FEATURE_OVERFLOW", "features")
    if chosen:
        return {"state": "confirmed", "items": chosen}
    return absence
