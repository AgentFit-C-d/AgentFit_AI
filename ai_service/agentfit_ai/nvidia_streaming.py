"""Bounded NVIDIA SSE normalization for the existing completion validators."""

import json

from .deepseek_evaluation import NVIDIA_REVIEW_MODELS
from .solar import AnalysisError, MAX_RESPONSE_BYTES, PROVIDER_WORKER_CODES, _json


MAX_STREAM_BYTES = 16 * 1024 * 1024
MAX_EVENT_BYTES = MAX_RESPONSE_BYTES
_STREAM_CODES = PROVIDER_WORKER_CODES | {'PROVIDER_MODEL', 'INCOMPLETE_RESPONSE'}
_FINISH_REASONS = frozenset(('stop', 'length', 'content_filter', 'tool_calls', 'function_call'))


def _sse_events(chunks):
    """Frame bytes before decoding UTF-8, so network splits cannot corrupt text."""
    pending, data = b'', []
    total, event_size = 0, 0
    for chunk in chunks:
        if type(chunk) is not bytes:
            raise AnalysisError('INVALID_RESPONSE')
        total += len(chunk)
        if total > MAX_STREAM_BYTES:
            raise AnalysisError('RESPONSE_TOO_LARGE')
        pending += chunk
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            event_size += len(line) + 1
            if event_size > MAX_EVENT_BYTES:
                raise AnalysisError('RESPONSE_TOO_LARGE')
            if line.endswith(b'\r'):
                line = line[:-1]
            if not line:
                if data:
                    yield b'\n'.join(data)
                data, event_size = [], 0
            elif line.startswith(b'data:'):
                value = line[5:]
                data.append(value[1:] if value.startswith(b' ') else value)
            elif line == b'data':
                data.append(b'')
            # SSE comments and metadata are never response content.
        if event_size + len(pending) > MAX_EVENT_BYTES:
            raise AnalysisError('RESPONSE_TOO_LARGE')
    # EOF is never a substitute for the protocol's terminal event.
    raise AnalysisError('INCOMPLETE_RESPONSE')


def _assemble_sse(chunks, expected_model):
    """Produce one complete envelope; ordinary JSON/schema checks still follow."""
    if type(expected_model) is not str or expected_model not in NVIDIA_REVIEW_MODELS:
        raise ValueError('unsupported streaming model')
    content, usage = [], {}
    content_bytes, model_seen, completion_id, finish = 0, False, None, None
    for raw in _sse_events(chunks):
        if raw == b'[DONE]':
            if finish is None:
                raise AnalysisError('INCOMPLETE_RESPONSE')
            if not model_seen:
                raise AnalysisError('PROVIDER_MODEL')
            envelope = {'model': expected_model, 'choices': [
                {'index': 0, 'finish_reason': finish,
                 'message': {'role': 'assistant', 'content': ''.join(content)}}], 'usage': usage}
            encoded = json.dumps(envelope, ensure_ascii=False).encode('utf-8')
            if len(encoded) > MAX_RESPONSE_BYTES:
                raise AnalysisError('RESPONSE_TOO_LARGE')
            return encoded
        event = _json(raw)
        if type(event) is not dict or 'error' in event:
            raise AnalysisError('INVALID_RESPONSE')
        if 'model' in event:
            if event['model'] != expected_model:
                raise AnalysisError('PROVIDER_MODEL')
            model_seen = True
        if 'id' in event:
            identity = event['id']
            if (type(identity) is not str or not identity or
                    (completion_id is not None and identity != completion_id)):
                raise AnalysisError('INVALID_RESPONSE')
            completion_id = identity
        if event.get('usage') is not None:
            if type(event['usage']) is not dict:
                raise AnalysisError('INVALID_RESPONSE')
            for name in ('prompt_tokens', 'completion_tokens'):
                value = event['usage'].get(name)
                if value is not None:
                    if type(value) is not int or value < 0:
                        raise AnalysisError('INVALID_RESPONSE')
                    usage[name] = value
        choices = event.get('choices')
        if type(choices) is not list or len(choices) > 1:
            raise AnalysisError('INVALID_RESPONSE')
        if not choices:
            continue
        choice = choices[0]
        if (type(choice) is not dict or type(choice.get('index')) is not int or
                choice['index'] != 0 or finish is not None):
            raise AnalysisError('INVALID_RESPONSE')
        delta = choice.get('delta')
        if delta is None:
            delta = {}
        if (type(delta) is not dict or delta.get('role') not in (None, 'assistant') or
                any(delta.get(name) for name in ('tool_calls', 'function_call', 'refusal'))):
            raise AnalysisError('INVALID_RESPONSE')
        for name in ('content', 'reasoning_content', 'reasoning'):
            if delta.get(name) is not None and type(delta[name]) is not str:
                raise AnalysisError('INVALID_RESPONSE')
        part = delta.get('content')
        if part is not None:
            try:
                content_bytes += len(part.encode('utf-8'))
            except UnicodeError:
                raise AnalysisError('INVALID_RESPONSE') from None
            if content_bytes > MAX_RESPONSE_BYTES:
                raise AnalysisError('RESPONSE_TOO_LARGE')
            content.append(part)
        reason = choice.get('finish_reason')
        if reason is not None:
            if type(reason) is not str or reason not in _FINISH_REASONS:
                raise AnalysisError('INVALID_RESPONSE')
            finish = reason
    raise AnalysisError('INCOMPLETE_RESPONSE')
