"""One SSE request in a disposable process; only complete responses cross stdout."""

from http.client import IncompleteRead
import math
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .deepseek_evaluation import NVIDIA_REVIEW_MODELS
from .nvidia_streaming import MAX_STREAM_BYTES, _STREAM_CODES, _assemble_sse
from .nvidia_response_diagnostics import encode_diagnostic, invalid_response
from .provider_worker import MAX_INPUT_BYTES
from .solar import AnalysisError, _NoRedirect, _json
import json


def _fetch(endpoint, payload, key, timeout):
    status, content_type = None, None
    request = Request(endpoint, data=json.dumps(payload).encode('utf-8'), method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
        'Accept': 'text/event-stream', 'Accept-Encoding': 'identity'})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            status, content_type = response.status, response.headers.get('Content-Type')
            if (response.status != 200 or response.headers.get_content_type() != 'text/event-stream' or
                    response.headers.get('Content-Encoding', 'identity').strip().lower() != 'identity'):
                raise invalid_response('http.headers')
            declared = response.headers.get('Content-Length')
            if declared is not None:
                if re.fullmatch(r'[0-9]{1,20}', declared) is None:
                    raise invalid_response('http.content_length')
                if int(declared) > MAX_STREAM_BYTES:
                    raise AnalysisError('RESPONSE_TOO_LARGE')
            def chunks():
                while True:
                    part = response.read1(8192)
                    if not part:
                        return
                    yield part
            return b'S' + _assemble_sse(chunks(), payload['model'])
    except HTTPError as error:
        status = error.code
        error.close()
        code = ('PROVIDER_AUTH' if status in (401, 403) else
                'PROVIDER_RATE_LIMIT' if status == 429 else
                'PROVIDER_REDIRECT' if 300 <= status < 400 else
                'PROVIDER_UNAVAILABLE' if status >= 500 else 'PROVIDER_REQUEST')
        return b'E' + code.encode('ascii')
    except (TimeoutError, URLError, OSError, IncompleteRead) as error:
        reason = error.reason if isinstance(error, URLError) else error
        code = 'PROVIDER_TIMEOUT' if isinstance(reason, TimeoutError) else 'PROVIDER_NETWORK'
        return b'E' + code.encode('ascii')
    except AnalysisError as error:
        code = error.code if error.code in _STREAM_CODES else 'PROVIDER_NETWORK'
        if code == 'INVALID_RESPONSE':
            diagnostic = encode_diagnostic(error, status, content_type, key)
            if diagnostic is not None:
                return b'D' + diagnostic
        return b'E' + code.encode('ascii')


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError('oversized request')
        request = _json(raw)
        if type(request) is not dict or set(request) != {'endpoint', 'payload', 'key', 'timeout'}:
            raise ValueError('invalid request')
        endpoint, payload, key, timeout = (request[name] for name in ('endpoint', 'payload', 'key', 'timeout'))
        if (type(endpoint) is not str or urlsplit(endpoint).scheme not in ('http', 'https') or
                not urlsplit(endpoint).hostname or urlsplit(endpoint).username is not None or
                type(payload) is not dict or type(payload.get('model')) is not str or
                payload['model'] not in NVIDIA_REVIEW_MODELS or payload.get('stream') is not True or
                type(key) is not str or not key.strip() or type(timeout) not in (int, float) or
                not 0 < timeout <= 600 or not math.isfinite(timeout)):
            raise ValueError('invalid request')
        output = _fetch(endpoint, payload, key, timeout)
    except Exception:
        output = b'EPROVIDER_NETWORK'
    sys.stdout.buffer.write(output)


if __name__ == '__main__':
    main()
