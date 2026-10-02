"""Exact, fail-closed source positions for optional LangExtract candidates."""

from collections import Counter

_DOUBLE_QUOTES = str.maketrans({'“': '"', '”': '"'})


def _unique_start(text: str, fragment: str) -> int | None:
    if not fragment:
        return None
    start = text.find(fragment)
    if start < 0 or text.find(fragment, start + 1) >= 0:
        return None
    return start


def _review(reason: str) -> dict:
    return {"status": "review", "start": None, "end": None, "reason": reason}


def ground_anchored_extractions(document: str, extractions: list, *,
                               allow_quote_variants: bool = False) -> tuple[dict, ...]:
    """Resolve only exact, unique source evidence without returning quotes."""
    if (type(document) is not str or type(extractions) is not list or
            type(allow_quote_variants) is not bool):
        raise ValueError("invalid grounding input")
    rows = []
    comparison_document = None
    resolved_positions = [None] * len(extractions)
    for index, item in enumerate(extractions):
        quote = getattr(item, "extraction_text", None)
        if (getattr(item, "extraction_class", None) != "candidate" or
                type(quote) is not str or not quote.strip()):
            rows.append(_review("invalid_candidate"))
            continue
        attributes = getattr(item, "attributes", None)
        if attributes is None:
            start = _unique_start(document, quote)
            reason = "unique_source"
        elif type(attributes) is dict and set(attributes) == {"anchor"}:
            anchor = attributes["anchor"]
            if type(anchor) is not str or not anchor.strip():
                rows.append(_review("invalid_anchor"))
                continue
            anchor_start = _unique_start(document, anchor)
            quote_start = _unique_start(anchor, quote)
            reason = "anchor"
            if (allow_quote_variants and anchor_start is None and anchor not in document
                    and quote_start is not None):
                # Only two 1-code-point quote variants are compared. CRLF,
                # Unicode composition, spaces, case and candidate text stay exact.
                if comparison_document is None:
                    comparison_document = document.translate(_DOUBLE_QUOTES)
                anchor_start = _unique_start(comparison_document, anchor.translate(_DOUBLE_QUOTES))
                reason = "anchor_quote_variant"
            if anchor_start is None or quote_start is None:
                rows.append(_review("ambiguous_anchor"))
                continue
            start = anchor_start + quote_start
            if document[start:start + len(quote)] != quote:
                rows.append(_review("ambiguous_anchor"))
                continue
        else:
            rows.append(_review("invalid_anchor"))
            continue
        if start is None:
            rows.append(_review("ambiguous_source"))
            continue
        end = start + len(quote)
        resolved_positions[index] = (start, end)
        interval = getattr(item, "char_interval", None)
        partial_match = (reason == "anchor" and
                         getattr(getattr(item, "alignment_status", None),
                                 "value", None) == "match_lesser")
        if interval is not None and not partial_match:
            library_start = getattr(interval, "start_pos", None)
            library_end = getattr(interval, "end_pos", None)
            if (type(library_start) is not int or type(library_end) is not int or
                    (library_start, library_end) != (start, end)):
                rows.append(_review("alignment_conflict"))
                continue
        rows.append({"status": "exact", "start": start, "end": end,
                     "reason": reason})
    counts = Counter(position for position in resolved_positions
                     if position is not None)
    seen_duplicates = set()
    result = []
    for row, position in zip(rows, resolved_positions):
        if position is not None and counts[position] > 1:
            duplicate_excess = int(position in seen_duplicates)
            seen_duplicates.add(position)
            result.append({**_review("duplicate_span"),
                           "duplicate_excess": duplicate_excess})
        else:
            result.append(row)
    return tuple(result)
