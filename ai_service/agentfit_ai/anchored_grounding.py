"""Exact, fail-closed source positions for optional LangExtract candidates."""

from collections import Counter


def _unique_start(text: str, fragment: str) -> int | None:
    if not fragment:
        return None
    start = text.find(fragment)
    if start < 0 or text.find(fragment, start + 1) >= 0:
        return None
    return start


def _review(reason: str) -> dict:
    return {"status": "review", "start": None, "end": None, "reason": reason}


def ground_anchored_extractions(document: str, extractions: list) -> tuple[dict, ...]:
    """Resolve only exact, unique source evidence without returning quotes."""
    if type(document) is not str or type(extractions) is not list:
        raise ValueError("invalid grounding input")
    rows = []
    for item in extractions:
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
            if anchor_start is None or quote_start is None:
                rows.append(_review("ambiguous_anchor"))
                continue
            start = anchor_start + quote_start
            reason = "anchor"
        else:
            rows.append(_review("invalid_anchor"))
            continue
        if start is None:
            rows.append(_review("ambiguous_source"))
            continue
        end = start + len(quote)
        interval = getattr(item, "char_interval", None)
        if interval is not None:
            library_start = getattr(interval, "start_pos", None)
            library_end = getattr(interval, "end_pos", None)
            if (type(library_start) is not int or type(library_end) is not int or
                    (library_start, library_end) != (start, end)):
                rows.append(_review("alignment_conflict"))
                continue
        rows.append({"status": "exact", "start": start, "end": end,
                     "reason": reason})
    counts = Counter((row["start"], row["end"]) for row in rows
                     if row["status"] == "exact")
    return tuple(_review("duplicate_span")
                 if row["status"] == "exact" and
                 counts[(row["start"], row["end"])] > 1 else row
                 for row in rows)
