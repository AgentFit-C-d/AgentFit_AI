"""One complete analysis in a disposable request process."""

import json
import sys

from .diagnostics import safe_code
from .recoverable_solar_analysis import RecoverableSolarAnalyzer
from .solar import AnalysisError, SolarAnalyzer, post_solar_inline
from .analysis_call_metadata import METADATA_VERSION, MODELS, unavailable_metadata, validate_metadata
from .candidate_confirmation import CONTRACT
from .candidate_review_dispositions import REVIEW_CONTRACT


MAX_INPUT_BYTES = 500_000
MAX_OUTPUT_BYTES = 1_500_000
FAILED = b'{"error":"ANALYSIS_WORKER_FAILED"}'


def execute_request(raw: bytes) -> bytes:
    metadata = None
    try:
        if len(raw) > MAX_INPUT_BYTES:
            return FAILED
        request = json.loads(raw)
        if (type(request) is not dict
                or any(type(request[name]) is not str for name in request)
                or not request.get("document") or not request.get("documentId")
                or not request.get("key", "").strip()):
            return FAILED
        mode = request.get('mode')
        expected = {"document", "documentId", "key"}
        if mode == 'integrated-candidates':
            expected |= {'mode', 'nvidiaKey'}
        elif mode in ('recoverable-solar', 'integrated-nvidia'):
            expected.add('mode')
        elif mode is not None:
            return FAILED
        if 'contract' in request:
            if mode != 'integrated-nvidia' or request['contract'] not in (CONTRACT, REVIEW_CONTRACT):
                return FAILED
            expected.add('contract')
        if 'diagnostics' in request:
            if mode != 'integrated-nvidia' or request['diagnostics'] != METADATA_VERSION:
                return FAILED
            expected.add('diagnostics')
            metadata = {}
        if 'reviewModel' in request:
            if mode != 'integrated-nvidia' or metadata is None or request['reviewModel'] not in MODELS:
                return FAILED
            expected.add('reviewModel')
        if set(request) != expected:
            return FAILED
        if mode == 'integrated-candidates':
            if not request['nvidiaKey'].strip():
                return FAILED
            from .candidate_service_worker import execute_integrated_analysis
            output = execute_integrated_analysis(request['document'], request['documentId'],
                                                  request['key'], request['nvidiaKey'])
        elif mode == 'integrated-nvidia':
            from .candidate_service_worker import execute_nvidia_analysis
            options = {'semantic_assessment': True}
            if request.get('contract') == REVIEW_CONTRACT:
                options['contract'] = REVIEW_CONTRACT
            if metadata is not None:
                options['call_diagnostics'] = metadata
            if 'reviewModel' in request:
                options['review_model'] = request['reviewModel']
            output = execute_nvidia_analysis(request['document'], request['documentId'], request['key'], **options)
        elif mode == 'recoverable-solar':
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
        if metadata is not None:
            output = {'version': METADATA_VERSION, 'result': output,
                      'diagnostics': validate_metadata(metadata) if metadata else unavailable_metadata('NOT_RETURNED')}
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
