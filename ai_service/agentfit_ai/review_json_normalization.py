"""Opt-in normalization of a single complete JSON fence; no value repair."""
import json

from .review_response_diagnostics import _JSON_FENCE, describe_review_response
from .solar import AnalysisError, MAX_RESPONSE_BYTES, _json


def _non_json_constant(_value):
    raise ValueError('non-JSON constant')


def normalize_review_json_fence(raw, expected_keys):
    """Return original bytes unless only a complete, correctly keyed JSON fence changes."""
    shape = describe_review_response(raw, expected_keys)
    if not (shape['issue'] == 'CONTENT_JSON' and shape['fenced_json'] and
            shape['fenced_object_keys_match']):
        return raw, False
    try:
        envelope = _json(raw)
        message = envelope['choices'][0]['message']
        inner = _JSON_FENCE.fullmatch(message['content'].strip()).group(1)
        # _json already checked duplicate keys; Python's optional non-JSON constants
        # must not make an otherwise invalid fenced document eligible for unwrapping.
        json.loads(inner, parse_constant=_non_json_constant)
        message['content'] = inner
        normalized = json.dumps(envelope, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(normalized) > MAX_RESPONSE_BYTES:
            return raw, False
        return normalized, True
    except (AnalysisError, RecursionError, TypeError, ValueError, UnicodeError):
        return raw, False
