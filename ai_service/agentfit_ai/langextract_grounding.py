"""Opt-in LangExtract alignment with exact source and repetition checks."""

from collections import Counter


_REVIEW = {"status": "review", "start": None, "end": None}


def validate_alignment(document: str, quotes: list[str], extractions) -> tuple[dict, ...]:
    """Accept only exact, uniquely accounted-for source spans; return no quotes."""
    if (type(document) is not str or type(quotes) is not list or
            any(type(quote) is not str or not quote for quote in quotes)):
        raise ValueError("invalid alignment input")
    aligned = list(extractions)
    if len(aligned) != len(quotes):
        raise ValueError("alignment changed candidate count")
    counts = Counter(quotes)
    rows = []
    positions = {}
    for index, (quote, item) in enumerate(zip(quotes, aligned)):
        if (getattr(item, "extraction_index", None) != index or
                getattr(item, "extraction_text", None) != quote):
            raise ValueError("alignment changed candidate identity")
        interval = getattr(item, "char_interval", None)
        start = getattr(interval, "start_pos", None)
        end = getattr(interval, "end_pos", None)
        if (type(start) is int and type(end) is int and
                0 <= start < end <= len(document) and
                document[start:end] == quote):
            positions.setdefault(quote, set()).add((start, end))
            rows.append({"status": "exact", "start": start, "end": end})
        else:
            rows.append(dict(_REVIEW))
    for index, quote in enumerate(quotes):
        if (document.count(quote) != counts[quote] or
                len(positions.get(quote, ())) != counts[quote]):
            rows[index] = dict(_REVIEW)
    return tuple(rows)


def align_with_langextract(document: str, quotes: list[str]) -> tuple[dict, ...]:
    """Run the optional library in memory; no model call or file output."""
    from langextract.data import Extraction
    from langextract.resolver import Resolver

    extractions = [Extraction("candidate", quote, extraction_index=index)
                   for index, quote in enumerate(quotes)]
    aligned = Resolver().align(
        extractions, document, token_offset=0, enable_fuzzy_alignment=False,
        accept_match_lesser=False, exact_alignment_algorithm="dp")
    return validate_alignment(document, quotes, aligned)
