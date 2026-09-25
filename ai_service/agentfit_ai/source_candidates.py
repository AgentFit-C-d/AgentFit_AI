"""Deterministic source boundary candidates; no semantic inference or source rewriting."""
import re

MAX_CANDIDATES = 12000
_WORD = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SUFFIX = re.compile(r"(?<=[가-힣])(?:입니다|이다|으로|에서|에게|을|를|은|는|이|가|과|와|로|도)$")

class CandidateLimitError(ValueError):
    pass

def source_candidates(document: str) -> list[dict]:
    tokens = []
    offset = 0
    for line_id, raw in enumerate(document.splitlines(keepends=True), 1):
        text = raw.rstrip("\r\n")
        for match in _WORD.finditer(text):
            suffix = _SUFFIX.search(match.group())
            cuts = ([match.start(), match.start()+suffix.start(), match.end()]
                    if suffix else [match.start(), match.end()])
            for begin, end in zip(cuts, cuts[1:]):
                if len(tokens) >= MAX_CANDIDATES:
                    raise CandidateLimitError("SOURCE_CANDIDATE_LIMIT")
                tokens.append({"id":len(tokens)+1, "lineId":line_id,
                               "start":offset+begin, "end":offset+end,
                               "text":text[begin:end]})
        offset += len(raw)
    return tokens

def candidate_table(tokens: list[dict]) -> str:
    """Render explicit IDs with JSON-escaped text, never source-supplied labels."""
    import json
    rows = []
    for token in tokens:
        rows.append(f"T{token['id']} L{token['lineId']} " + json.dumps(token["text"], ensure_ascii=False))
    return "\n".join(rows)
