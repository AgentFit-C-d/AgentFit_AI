"""One complete Solar analysis in a disposable request process."""

import json
import sys

from .diagnostics import safe_code
from .recoverable_solar_analysis import RecoverableSolarAnalyzer
from .solar import AnalysisError, SolarAnalyzer, post_solar_inline


MAX_INPUT_BYTES = 500_000
MAX_OUTPUT_BYTES = 1_500_000
FAILED = b'{"error":"ANALYSIS_WORKER_FAILED"}'


def execute_request(raw: bytes) -> bytes:
    try:
        if len(raw) > MAX_INPUT_BYTES:
            return FAILED
        request = json.loads(raw)
        if (type(request) is not dict or set(request) not in
                ({"document", "documentId", "key"},
                 {"document", "documentId", "key", "mode"})
                or any(type(request[name]) is not str for name in request)
                or not request["document"] or not request["documentId"] or not request["key"]
                or ("mode" in request and request["mode"] != "recoverable-solar")):
            return FAILED
        if "mode" in request:
            output = RecoverableSolarAnalyzer(
                request["key"], transport=post_solar_inline,
                analysis_timeout_seconds=40).analyze_recoverable(
                    request["document"], request["documentId"])
        else:
            result = SolarAnalyzer(request["key"], transport=post_solar_inline,
                                   analysis_timeout_seconds=40).analyze(
                                       request["document"], request["documentId"])
            output = {"outcome": "complete", "profile": result.profile}
    except AnalysisError as error:
        output = {"error": safe_code(error.code)}
    except Exception:
        return FAILED
    try:
        encoded = json.dumps(output, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        return FAILED
    return encoded if len(encoded) <= MAX_OUTPUT_BYTES else FAILED


def main() -> None:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    sys.stdout.buffer.write(execute_request(raw))


if __name__ == "__main__":
    main()
