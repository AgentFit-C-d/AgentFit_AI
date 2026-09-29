"""Source-exact context choices for opt-in evidence repair."""

from .profile import FIELDS


LOCATION_REASONS = frozenset({"AMBIGUOUS_QUOTE", "AMBIGUOUS_CONTEXT",
                              "CONTEXT_NOT_FOUND", "QUOTE_NOT_IN_CONTEXT"})
PADDING = (8, 16, 32, 64, 128, 240)


def _positions(text, fragment):
    found = []
    start = -1
    while True:
        start = text.find(fragment, start + 1)
        if start < 0:
            return found
        found.append(start)


def _unique_context(document, quote, position):
    end = position + len(quote)
    line_start = document.rfind("\n", 0, position) + 1
    line_end = document.find("\n", position)
    if line_end < 0:
        line_end = len(document)
    if end > line_end:
        return None
    for padding in PADDING:
        start = max(line_start, position - padding)
        stop = min(line_end, end + padding)
        context = document[start:stop]
        if (len(context) <= 240 and len(_positions(document, context)) == 1
                and len(_positions(context, quote)) == 1):
            return context
    return None


def build_repair_context_options(document, errors, previous):
    """Return complete source-choice sets for location errors, or omit them."""
    if type(document) is not str or type(errors) is not list or type(previous) is not dict:
        return {}
    result = {}
    for error in errors:
        if type(error) is not dict or error.get("code") != "INVALID_EVIDENCE":
            continue
        field, detail = error.get("field"), error.get("detail")
        if field not in FIELDS or type(detail) is not dict or detail.get(
                "reason") not in LOCATION_REASONS:
            continue
        index = detail.get("itemIndex")
        candidate = previous.get(field)
        if (type(index) is not int or type(candidate) is not dict
                or candidate.get("state") != "confirmed"
                or type(candidate.get("items")) is not list
                or not 0 <= index < len(candidate["items"])):
            continue
        item = candidate["items"][index]
        quote = item.get("quote") if type(item) is dict else None
        if type(quote) is not str or not quote.strip() or len(quote) > 240:
            continue
        positions = _positions(document, quote)
        if not 1 <= len(positions) <= 8:
            continue
        contexts = [_unique_context(document, quote, position) for position in positions]
        if any(context is None for context in contexts):
            continue
        result[field] = {"itemIndex": index,
                         "options": [{"quote": quote, "context": context}
                                     for context in contexts]}
    return result
