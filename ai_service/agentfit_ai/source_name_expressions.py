"""Find an existing parenthetical name expression at confirmed source positions."""

import re

from .profile import MAX_TEXT_CODE_POINTS


_OPEN = re.compile(r'[ \t]*([(（])[ \t]*')
_CLOSE = {'(': re.compile(r'[ \t]*\)'), '（': re.compile(r'[ \t]*）')}


def source_name_expression(document, entries):
    """Return source text and its span, without asserting that names are aliases."""
    if type(document) is not str or type(entries) is not list:
        raise ValueError('invalid name entries')
    by_start, values = {}, set()
    for entry in entries:
        if type(entry) not in (tuple, list) or len(entry) != 2:
            raise ValueError('invalid name entry')
        value, span = entry
        if (type(value) is not str or not value.strip() or type(span) is not dict or
                set(span) != {'start', 'end'} or type(span['start']) is not int or
                type(span['end']) is not int or
                not 0 <= span['start'] < span['end'] <= len(document) or
                document[span['start']:span['end']] != value):
            raise ValueError('invalid name span')
        values.add(value)
        by_start.setdefault(span['start'], []).append((value, span))
    if len(values) < 2:
        return None
    proofs = []
    for left, span in entries:
        opening = _OPEN.match(document, span['end'])
        if opening is None:
            continue
        for right, right_span in by_start.get(opening.end(), []):
            closing = _CLOSE[opening.group(1)].match(document, right_span['end'])
            if closing is None or left == right:
                continue
            expression = document[span['start']:closing.end()]
            if len(expression) > MAX_TEXT_CODE_POINTS or len(expression.splitlines()) != 1:
                continue
            proofs.append((span['start'], closing.end(), expression, frozenset((left, right))))
    for start, end, expression, parts in sorted(proofs, key=lambda item: (item[0], item[1])):
        allowed = parts | {other[2] for other in proofs if other[3] == parts}
        if values <= allowed:
            return expression, {'start': start, 'end': end}
    return None
