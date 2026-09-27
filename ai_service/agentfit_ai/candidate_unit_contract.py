"""Opt-in keyed candidate responses and source-exact normalization."""

from .candidate_occurrences import CANDIDATE_EXPANSION_PROMPT
from .sections import Section
from .solar import AnalysisError, _object


_OUTPUT_INSTRUCTION = (
    '출력 JSON: {"units":[{"unitId":"공급된 ID","quotes":["원문 그대로 인용"]}]}.'
    '\n공급된 모든 unitId를 정확히 한 번 반환한다. 후보가 없으면 quotes=[].'
)
_KEYED_OUTPUT_INSTRUCTION = (
    '출력 JSON: {"units":{"U0001":["원문 그대로 인용"]}}.'
    '\n공급된 모든 unitId를 units 객체의 필수 키로 반환한다. 후보가 없으면 해당 키의 값은 [].'
)
if _OUTPUT_INSTRUCTION not in CANDIDATE_EXPANSION_PROMPT:
    raise RuntimeError("candidate prompt output instruction changed")
KEYED_CANDIDATE_PROMPT = CANDIDATE_EXPANSION_PROMPT.replace(
    _OUTPUT_INSTRUCTION, _KEYED_OUTPUT_INSTRUCTION, 1
)


def keyed_candidate_schema(batch: list[Section]) -> dict:
    return _object({"units": _object({section.id: {
        "type": "array", "maxItems": 30,
        "items": {"type": "string", "minLength": 1, "maxLength": 2000},
    } for section in batch})})


def _invalid(reason: str):
    error = AnalysisError("ANCHORED_CANDIDATE")
    error.candidate_detail = {"reason": reason}
    raise error


def normalize_keyed_candidates(
    replies: list[dict], batches: list[list[Section]], source_units: list[Section]
) -> tuple[list[dict], dict]:
    """Validate all keyed replies before assigning source-exact candidate IDs."""
    if (type(replies) is not list or type(batches) is not list or
            type(source_units) is not list or not source_units or len(replies) != len(batches)):
        _invalid("invalid_shape")
    sources = {section.id: section for section in source_units}
    batch_ids = [section.id for batch in batches for section in batch]
    if len(sources) != len(source_units) or len(batch_ids) != len(sources) or set(batch_ids) != set(sources):
        _invalid("invalid_shape")

    selected: set[tuple[str, str]] = set()
    remapped = deduplicated = 0
    for reply, batch in zip(replies, batches):
        if type(reply) is not dict or set(reply) != {"units"} or type(reply["units"]) is not dict:
            _invalid("invalid_shape")
        groups = reply["units"]
        if set(groups) != {section.id for section in batch}:
            _invalid("missing_or_extra_unit")
        for section in batch:
            quotes = groups[section.id]
            if (type(quotes) is not list or len(quotes) > 30 or
                    any(type(q) is not str or not q.strip() or len(q) > 2000 for q in quotes)):
                _invalid("invalid_quote")
            if len(quotes) != len(set(quotes)):
                _invalid("invalid_quote")
            for quote in quotes:
                target = section
                if quote not in section.text:
                    matches = [unit for unit in source_units if quote in unit.text]
                    if not matches:
                        _invalid("not_in_source")
                    if len(matches) != 1:
                        _invalid("ambiguous_unit")
                    target = matches[0]
                    remapped += 1
                pair = (target.id, quote)
                if pair in selected:
                    deduplicated += 1
                selected.add(pair)

    positions = []
    for unit_id, quote in selected:
        section = sources[unit_id]
        index = section.text.find(quote)
        while index >= 0:
            positions.append((section.start + index, section.start + index + len(quote), unit_id, quote))
            if len(positions) > 120:
                raise AnalysisError("SECTION_LIMIT")
            index = section.text.find(quote, index + 1)
    positions.sort(key=lambda item: (item[0], item[1], item[3]))
    pool = [{"id": "F" + str(i).zfill(4), "unitId": unit_id, "quote": quote,
             "span": {"start": start, "end": end}}
            for i, (start, end, unit_id, quote) in enumerate(positions, 1)]
    return pool, {"remapped": remapped, "deduplicated": deduplicated}
