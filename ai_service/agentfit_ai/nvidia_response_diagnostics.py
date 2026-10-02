"""Bounded, credential-suppressed failure metadata. Never changes response validation."""
import json
import re

from .solar import AnalysisError

MAX_EXCERPT_BYTES = 2048
MAX_CONTENT_TYPE_BYTES = 128
MAX_DIAGNOSTIC_BYTES = 8192
_LOCATIONS = frozenset(('http.headers', 'http.content_length', 'sse.chunk_type',
    'sse.json', 'sse.event', 'sse.id', 'sse.usage', 'sse.usage.prompt_tokens',
    'sse.usage.completion_tokens', 'sse.choices', 'sse.choice', 'sse.delta',
    'sse.delta.content', 'sse.delta.reasoning', 'sse.delta.reasoning_content',
    'sse.content_utf8', 'sse.finish_reason'))
_CREDENTIAL = re.compile(r'authorization|api[\s_-]*key|access[\s_-]*token|'
                         r'bearer\b|basic\b|nvapi-|\bsk-[a-z0-9]{12}', re.I)
_UNICODE_ESCAPE = re.compile(r'\\u([0-9a-fA-F]{4})')


def invalid_response(location, raw=None, index=None):
    """Attach transient context only; the worker sanitizes it before serialization."""
    error = AnalysisError('INVALID_RESPONSE')
    error._response_failure = (location, raw, index)
    return error


def _excerpt(text, key, limit):
    # Inspect the entire bounded event BEFORE truncation, including JSON-escaped keys.
    normalized = _UNICODE_ESCAPE.sub(lambda m: chr(int(m[1], 16)), text).replace('\\/', '/')
    secrets = (key, json.dumps(key)[1:-1], json.dumps(key, ensure_ascii=False)[1:-1]) if key else ()
    # NUL-separated encodings/values can conceal a credential from text matching.
    # Omit this excerpt instead of changing the original JSON parser's encoding rules.
    if ('\x00' in normalized or
            any(secret in text or secret in normalized for secret in secrets) or _CREDENTIAL.search(normalized)):
        return '[REDACTED]', False, True
    encoded = text.encode('utf-8', errors='replace')
    return encoded[:limit].decode('utf-8', errors='ignore'), len(encoded) > limit, False


def encode_diagnostic(error, status, content_type, key):
    """Best effort; failure to record must leave the original error code intact."""
    try:
        location, raw, index = error._response_failure
        if location not in _LOCATIONS:
            return None
        record = {'version': 1, 'http_status': status,
                  'content_type': None if content_type is None else
                      _excerpt(content_type, key, MAX_CONTENT_TYPE_BYTES)[0],
                  'error_location': location, 'sse_event': None}
        if type(raw) is bytes:
            excerpt, truncated, redacted = _excerpt(raw.decode('utf-8', errors='replace'), key, MAX_EXCERPT_BYTES)
            failed = dict(index=index, data_bytes=len(raw), excerpt=excerpt,
                          truncated=truncated, redacted=redacted, json_error=None)
            if location == 'sse.json':
                # Diagnostic-only reparse: never supplies data to the real response parser.
                try:
                    json.loads(raw)
                except json.JSONDecodeError as exc:
                    failed['json_error'] = {'char': exc.pos, 'line': exc.lineno, 'column': exc.colno}
                except (ValueError, UnicodeError):
                    pass
            record['sse_event'] = failed
        encoded = json.dumps(record, ensure_ascii=False).encode('utf-8')
        while len(encoded) > MAX_DIAGNOSTIC_BYTES and record['sse_event']['excerpt']:
            failed['excerpt'] = failed['excerpt'][:len(failed['excerpt']) // 2]
            failed['truncated'] = True
            encoded = json.dumps(record, ensure_ascii=False).encode('utf-8')
        return encoded if len(encoded) <= MAX_DIAGNOSTIC_BYTES else None
    except Exception:
        return None


def decode_diagnostic(raw, key):
    """Allowlist the private child envelope; untrusted extra fields cannot reach a log."""
    try:
        if len(raw) > MAX_DIAGNOSTIC_BYTES:
            return None
        record = json.loads(raw)
        if (type(record) is not dict or set(record) !=
                {'version', 'http_status', 'content_type', 'error_location', 'sse_event'} or
                type(record['version']) is not int or record['version'] != 1 or
                record['error_location'] not in _LOCATIONS):
            return None
        if record['http_status'] is not None and (type(record['http_status']) is not int or
                                                 not 100 <= record['http_status'] <= 599):
            return None
        content_type = record['content_type']
        if content_type is not None:
            if type(content_type) is not str or len(content_type.encode()) > MAX_CONTENT_TYPE_BYTES:
                return None
            record['content_type'] = _excerpt(content_type, key, MAX_CONTENT_TYPE_BYTES)[0]
        failed = record['sse_event']
        if failed is not None:
            if (type(failed) is not dict or set(failed) !=
                    {'index', 'data_bytes', 'excerpt', 'truncated', 'redacted', 'json_error'} or
                    type(failed['index']) is not int or failed['index'] < 1 or
                    type(failed['data_bytes']) is not int or not 0 <= failed['data_bytes'] <= 1_048_576 or
                    type(failed['excerpt']) is not str or len(failed['excerpt'].encode()) > MAX_EXCERPT_BYTES or
                    type(failed['truncated']) is not bool or type(failed['redacted']) is not bool):
                return None
            position = failed['json_error']
            if position is not None and (type(position) is not dict or
                    set(position) != {'char', 'line', 'column'} or
                    any(type(v) is not int or v < 0 for v in position.values())):
                return None
            excerpt, _, redacted = _excerpt(failed['excerpt'], key, MAX_EXCERPT_BYTES)
            failed.update(excerpt=excerpt, redacted=failed['redacted'] or redacted)
        return record
    except Exception:
        return None
