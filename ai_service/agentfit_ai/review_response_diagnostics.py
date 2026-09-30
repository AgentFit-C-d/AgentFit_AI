"""Bounded shape-only observations; never a response repair or validity verdict."""
import re

from .solar import AnalysisError, MAX_RESPONSE_BYTES, _json


def _kind(value):
    if value is None:
        return 'null'
    return {dict: 'object', list: 'array', str: 'string', bool: 'boolean',
            int: 'number', float: 'number'}.get(type(value), 'other')


def describe_review_response(raw, expected_keys):
    """Return fixed enums/counts only, without echoing provider text or key names."""
    if (type(expected_keys) not in (tuple, list) or not 1 <= len(expected_keys) <= 32 or
            any(type(key) is not str or not key for key in expected_keys) or
            len(set(expected_keys)) != len(expected_keys)):
        raise ValueError('invalid response diagnostic keys')
    expected = set(expected_keys)
    result = {'issue': None, 'content_kind': None, 'content_chars': None,
              'json_kind': None, 'missing_key_count': None, 'unexpected_key_count': None,
              'fenced_json': False, 'fenced_object_keys_match': None}

    def fail(issue):
        result['issue'] = issue
        return result

    if type(raw) is not bytes:
        return fail('RAW_TYPE')
    if len(raw) > MAX_RESPONSE_BYTES:
        return fail('RAW_SIZE')
    try:
        envelope = _json(raw)
    except (AnalysisError, RecursionError):
        return fail('ENVELOPE_JSON')
    if type(envelope) is not dict:
        return fail('ENVELOPE_ROOT')
    choices = envelope.get('choices')
    if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
        return fail('CHOICES_SHAPE')
    choice = choices[0]
    message = choice.get('message')
    if type(message) is not dict:
        return fail('MESSAGE_SHAPE')
    if message.get('refusal'):
        return fail('REFUSAL')
    if message.get('tool_calls'):
        return fail('TOOLS')
    if choice.get('finish_reason') != 'stop':
        return fail('NON_STOP_FINISH')
    content = message.get('content')
    result['content_kind'] = _kind(content)
    if type(content) is not str:
        return fail('CONTENT_TYPE')
    result['content_chars'] = len(content)
    try:
        value = _json(content)
    except (AnalysisError, RecursionError):
        fence = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```',
                             content.strip(), re.DOTALL | re.IGNORECASE)
        if fence:
            try:
                inner = _json(fence.group(1))
                result['fenced_json'] = True
                result['fenced_object_keys_match'] = type(inner) is dict and set(inner) == expected
            except (AnalysisError, RecursionError):
                pass
        return fail('CONTENT_JSON')
    result['json_kind'] = _kind(value)
    if type(value) is not dict:
        return fail('CONTENT_ROOT')
    result['missing_key_count'] = len(expected - value.keys())
    result['unexpected_key_count'] = len(value.keys() - expected)
    if set(value) != expected:
        return fail('CONTENT_KEYS')
    return result
