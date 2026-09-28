"""One Provider HTTP call in a disposable, time-bounded child process."""

import json
import re
import sys
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .solar import MAX_RESPONSE_BYTES, _NoRedirect


MAX_INPUT_BYTES = 10_485_760


def _fetch(endpoint: str, payload: dict, key: str, timeout: float) -> bytes:
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Accept-Encoding": "identity",
    }, method="POST")
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                return b"EINVALID_RESPONSE"
            declared = response.headers.get("Content-Length")
            if declared is not None:
                if re.fullmatch(r"[0-9]{1,20}", declared) is None:
                    return b"EINVALID_RESPONSE"
                if int(declared) > MAX_RESPONSE_BYTES:
                    return b"ERESPONSE_TOO_LARGE"
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                return b"ERESPONSE_TOO_LARGE"
            if declared is not None and len(raw) != int(declared):
                return b"EPROVIDER_NETWORK"
            return b"S" + raw
    except HTTPError as error:
        status = error.code
        error.close()
        code = ("PROVIDER_AUTH" if status in (401, 403) else
                "PROVIDER_RATE_LIMIT" if status == 429 else
                "PROVIDER_REDIRECT" if 300 <= status < 400 else
                "PROVIDER_UNAVAILABLE" if status >= 500 else "PROVIDER_REQUEST")
        return b"E" + code.encode("ascii")
    except (TimeoutError, URLError, OSError, IncompleteRead) as error:
        reason = error.reason if isinstance(error, URLError) else error
        code = "PROVIDER_TIMEOUT" if isinstance(reason, TimeoutError) else "PROVIDER_NETWORK"
        return b"E" + code.encode("ascii")


def main() -> None:
    try:
        input_bytes = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(input_bytes) > MAX_INPUT_BYTES:
            raise ValueError("oversized request")
        request = json.loads(input_bytes)
        if (type(request) is not dict or set(request) != {"endpoint", "payload", "key", "timeout"}
                or type(request["endpoint"]) is not str or type(request["payload"]) is not dict
                or type(request["key"]) is not str or type(request["timeout"]) not in (int, float)
                or request["timeout"] <= 0):
            raise ValueError("invalid request")
        output = _fetch(request["endpoint"], request["payload"], request["key"],
                        request["timeout"])
    except Exception:
        output = b"EPROVIDER_NETWORK"
    sys.stdout.buffer.write(output)


if __name__ == "__main__":
    main()
