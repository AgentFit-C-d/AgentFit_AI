"""Evaluation-only observation around the current worker in a disposable process.

The caller owns free-access authorization and the parent process deadline.
No prompt, model, schema, classification or response rule is replaced here.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
from time import monotonic

from agentfit_ai import analysis_worker, candidate_service_worker
from agentfit_ai.candidate_confirmation import CONTRACT
from agentfit_ai.candidate_review_dispositions import REVIEW_CONTRACT
from agentfit_ai.diagnostics import safe_code
from agentfit_ai.nvidia_response_diagnostics import _excerpt
from .candidate_trace import CandidateTrace

MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_RECORDING_BYTES = 32 * 1024 * 1024


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _extractions(rows):
    return [{'extraction_class': getattr(row, 'extraction_class', None),
             'extraction_text': getattr(row, 'extraction_text', None),
             'attributes': getattr(row, 'attributes', None),
             'char_interval': (None if getattr(row, 'char_interval', None) is None else
                               {'start': row.char_interval.start_pos,
                                'end': row.char_interval.end_pos})}
            for row in rows]


class DocumentRecorder:
    def __init__(self, document, document_id, key, *, contract=CONTRACT):
        self.document, self.document_id, self.key = document, document_id, key
        self.provenance = CandidateTrace(document, document_id, contract=contract)
        self.started = monotonic()
        self.recording_seconds = 0.0
        self.size = 0
        self.value = {'version': 'document-profile-trace-v1', 'documentId': document_id,
                      'sourceSha256': hashlib.sha256(document.encode('utf-8')).hexdigest(),
                      'status': 'partial', 'stages': {}, 'calls': [],
                      'stageElapsedMs': {}, 'observationErrors': []}

    def failure(self, code):
        if code not in self.value['observationErrors']:
            self.value['observationErrors'].append(code)

    def copy_record(self, value):
        encoded = _encode(value)
        text, truncated, redacted = _excerpt(encoded.decode('utf-8'), self.key, MAX_RECORD_BYTES)
        if truncated or redacted or self.size + len(encoded) > MAX_RECORDING_BYTES:
            self.failure('RECORD_REDACTED' if redacted else 'RECORD_LIMIT')
            return None
        self.size += len(encoded)
        return json.loads(text)

    def observe(self, stage, state, *, legacy=False):
        started = monotonic()
        try:
            if legacy:
                self.provenance.observe(stage, state)
            if stage in self.value['stages']:
                raise ValueError('duplicate observation')
            record = self.copy_record(_extractions(state) if stage == 'general_extracted' else state)
            if record is not None:
                self.value['stages'][stage] = record
                self.value['stageElapsedMs'][stage] = round((monotonic() - self.started) * 1000, 3)
        except Exception:
            self.failure('OBSERVATION_FAILED')
        finally:
            self.recording_seconds += monotonic() - started

    def transport(self, send):
        def captured(payload, key, timeout):
            row = {'index': len(self.value['calls']) + 1, 'request': None,
                   'response': None, 'error': None, 'responseDiagnostic': None}
            recording = monotonic()
            try:
                row['request'] = self.copy_record(payload)
            except Exception:
                self.failure('REQUEST_RECORD_FAILED')
            self.recording_seconds += monotonic() - recording
            started = monotonic()
            raw = None
            try:
                raw = send(payload, key, timeout)
                return raw
            except Exception as error:
                row['error'] = safe_code(getattr(error, 'code', None))
                try:
                    diagnostic = getattr(error, 'response_diagnostic', None)
                    row['responseDiagnostic'] = self.copy_record(diagnostic) if diagnostic else None
                except Exception:
                    self.failure('DIAGNOSTIC_RECORD_FAILED')
                raise
            finally:
                row['elapsedMs'] = round((monotonic() - started) * 1000, 3)
                recording = monotonic()
                try:
                    if raw is not None:
                        text, truncated, redacted = _excerpt(raw.decode('utf-8'), key, MAX_RECORD_BYTES)
                        row['response'] = self.copy_record({'text': text, 'bytes': len(raw),
                                                            'truncated': truncated, 'redacted': redacted})
                        if truncated or redacted:
                            self.failure('RESPONSE_RECORD_INCOMPLETE')
                    self.value['calls'].append(row)
                except Exception:
                    self.failure('RESPONSE_RECORD_FAILED')
                self.recording_seconds += monotonic() - recording
        return captured

    def finish_analysis(self, result):
        try:
            self.provenance.finish(result)
        except Exception:
            self.failure('PROVENANCE_FAILED')

    def finish(self, output):
        try:
            result = json.loads(output)
            if 'diagnostics' in result:
                self.observe('call_metadata', result['diagnostics'])
                result = result['result']
            self.observe('final_response', result)
            self.value['provenance'] = self.provenance.summary()
            if (not self.value['observationErrors'] and result.get('outcome') != 'failed'
                    and self.value['provenance']['status'] == 'complete'):
                self.value['status'] = 'complete'
        except Exception:
            self.failure('FINAL_RECORD_FAILED')
        self.value['elapsedMs'] = round((monotonic() - self.started) * 1000, 3)
        self.value['recordingMs'] = round(self.recording_seconds * 1000, 3)
        return self.value


def observe_request(raw: bytes) -> tuple[bytes, dict]:
    """Internal worker entry. Never invoke concurrently or install in the server."""
    if len(raw) > analysis_worker.MAX_INPUT_BYTES:
        raise ValueError('INVALID_EVALUATION_REQUEST')
    request = json.loads(raw)
    if (request.get('mode') != 'integrated-nvidia' or 'reviewModel' in request or
            request.get('contract', CONTRACT) not in (CONTRACT, REVIEW_CONTRACT) or
            set(request) - {'document', 'documentId', 'key', 'mode', 'diagnostics', 'contract'}):
        raise ValueError('INVALID_EVALUATION_REQUEST')
    recorder = DocumentRecorder(request['document'], request['documentId'], request['key'],
                                contract=request.get('contract', CONTRACT))
    original_analyze = candidate_service_worker.analyze_nvidia_candidates
    original_send = candidate_service_worker.post_nvidia_streaming_inline

    def observed(*args, **kwargs):
        # execute_request supplies semantic_assessment=True; keep every other default.
        result = original_analyze(*args, **kwargs,
            observer=lambda s, p: recorder.observe(s, p, legacy=True),
            detail_observer=recorder.observe)
        recorder.finish_analysis(result)
        return result

    candidate_service_worker.analyze_nvidia_candidates = observed
    candidate_service_worker.post_nvidia_streaming_inline = recorder.transport(original_send)
    try:
        output = analysis_worker.execute_request(raw)
    finally:
        candidate_service_worker.analyze_nvidia_candidates = original_analyze
        candidate_service_worker.post_nvidia_streaming_inline = original_send
    return output, recorder.finish(output)


def execute_observed_request(raw: bytes, trace_path: Path) -> bytes:
    output = analysis_worker.FAILED
    try:
        if (not trace_path.is_absolute() or trace_path.exists() or trace_path.is_symlink()
                or trace_path.parent.resolve() != trace_path.parent or not trace_path.parent.is_dir()):
            return output
        staged = trace_path.with_name(trace_path.name + '.staged')
        with staged.open('xb') as handle:
            output, trace = observe_request(raw)
            encoded = _encode(trace)
            if len(encoded) > MAX_RECORDING_BYTES:
                trace = {'version': 'document-profile-trace-v1', 'status': 'unavailable',
                         'observationErrors': ['RECORD_LIMIT']}
                encoded = _encode(trace)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(staged, trace_path)
    except Exception:
        # Sidecar failure cannot change the existing service result. No raw errors.
        pass
    return output


def main():
    if len(sys.argv) != 2:
        sys.stdout.buffer.write(analysis_worker.FAILED)
        return
    raw = sys.stdin.buffer.read(analysis_worker.MAX_INPUT_BYTES + 1)
    sys.stdout.buffer.write(execute_observed_request(raw, Path(sys.argv[1])))


if __name__ == '__main__':
    main()
