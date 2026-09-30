"""Opt-in observer in a disposable analysis process; stdout keeps its old contract."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from agentfit_ai import analysis_worker, candidate_service_worker
from agentfit_ai.analysis_call_metadata import METADATA_VERSION
from .candidate_trace import CandidateTrace, MAX_TRACE_BYTES, validate_trace

VERSION = 'candidate-provenance-worker-v1'
MODEL = 'deepseek-ai/deepseek-v4.1-flash'
ERRORS = ('NOT_INVOKED', 'OBSERVATION_FAILED', 'TRACE_TOO_LARGE')


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _identity(document, document_id):
    if (type(document) is not str or not document.strip() or len(document) > 100_000
            or type(document_id) is not str or re.fullmatch(r'PUBLIC-[0-9]{2}', document_id) is None):
        raise ValueError('INVALID_PROBE_REPORT')
    return hashlib.sha256(document.encode('utf-8')).hexdigest()


def validate_probe_report(document: str, document_id: str, value: dict) -> dict:
    """Accept only bounded, source-bound observations and fixed failure codes."""
    try:
        digest = _identity(document, document_id)
        if (type(value) is not dict or set(value) != {
                'version', 'documentId', 'sourceSha256', 'status', 'error', 'trace'}
                or value['version'] != VERSION or value['documentId'] != document_id
                or value['sourceSha256'] != digest or len(_encode(value)) > MAX_TRACE_BYTES):
            raise ValueError
        if value['status'] == 'available' and value['error'] is None:
            validate_trace(document, document_id, value['trace'])
        elif not (value['status'] == 'unavailable' and type(value['error']) is str
                  and value['error'] in ERRORS and value['trace'] is None):
            raise ValueError
        return deepcopy(value)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        raise ValueError('INVALID_PROBE_REPORT') from None


def _request(raw):
    if type(raw) is not bytes or len(raw) > analysis_worker.MAX_INPUT_BYTES:
        raise ValueError
    request = json.loads(raw)
    if (type(request) is not dict or set(request) != {
            'document', 'documentId', 'key', 'mode', 'diagnostics', 'reviewModel'}
            or any(type(value) is not str for value in request.values())
            or request['mode'] != 'integrated-nvidia' or request['diagnostics'] != METADATA_VERSION
            or request['reviewModel'] != MODEL or not request['key'].strip() or len(request['key']) > 4096):
        raise ValueError
    _identity(request['document'], request['documentId'])
    return request


def _observe_request(raw, request):
    document, document_id = request['document'], request['documentId']
    report = {'version': VERSION, 'documentId': document_id,
              'sourceSha256': _identity(document, document_id),
              'status': 'unavailable', 'error': 'NOT_INVOKED', 'trace': None}
    original = candidate_service_worker.analyze_nvidia_candidates

    def observed(*args, **kwargs):
        recorder, failed = None, False
        try:
            recorder = CandidateTrace(document, document_id)
        except Exception:
            failed = True

        def observe(stage, state):
            nonlocal failed
            if not failed:
                try:
                    recorder.observe(stage, state)
                except Exception:
                    failed = True

        try:
            result = original(*args, **kwargs, observer=observe)
            if not failed:
                try:
                    recorder.finish(result)
                except Exception:
                    failed = True
            return result
        finally:
            try:
                if failed:
                    raise ValueError
                trace = recorder.summary()
                validate_trace(document, document_id, trace)
                report.update(status='available', error=None, trace=trace)
            except Exception:
                report.update(status='unavailable', error='OBSERVATION_FAILED', trace=None)

    # This hook is confined to one disposable process, never the HTTP service.
    candidate_service_worker.analyze_nvidia_candidates = observed
    try:
        output = analysis_worker.execute_request(raw)
    finally:
        candidate_service_worker.analyze_nvidia_candidates = original
    try:
        if len(_encode(report)) > MAX_TRACE_BYTES:
            report.update(status='unavailable', error='TRACE_TOO_LARGE', trace=None)
        encoded = _encode(validate_probe_report(document, document_id, report))
    except Exception:
        report.update(status='unavailable', error='OBSERVATION_FAILED', trace=None)
        encoded = _encode(report)
    return output, encoded


def execute_probe_request(raw: bytes, trace_path: Path) -> bytes:
    """Reserve a new sidecar before analysis; a failed write never changes stdout."""
    output = analysis_worker.FAILED
    try:
        request = _request(raw)
        if (not trace_path.is_absolute() or trace_path.is_symlink() or trace_path.exists()
                or not trace_path.parent.is_dir() or trace_path.parent.resolve() != trace_path.parent):
            return output
        with trace_path.open('xb') as handle:
            output, encoded = _observe_request(raw, request)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # An empty/partial sidecar must fail parent validation. Never print errors
        # containing input, paths, API keys, or provider responses.
        pass
    return output


def main() -> None:
    if len(sys.argv) != 2:
        sys.stdout.buffer.write(analysis_worker.FAILED)
        return
    raw = sys.stdin.buffer.read(analysis_worker.MAX_INPUT_BYTES + 1)
    sys.stdout.buffer.write(execute_probe_request(raw, Path(sys.argv[1])))


if __name__ == '__main__':
    main()
