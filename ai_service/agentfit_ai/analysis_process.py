"""Run one complete analysis in a disposable child with a request deadline."""

import asyncio
import json
import sys
from pathlib import Path

from .analysis_worker import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES
from .candidate_confirmation import CONTRACT, validate_candidate_confirmation
from .candidate_review_dispositions import REVIEW_CONTRACT
from .diagnostics import safe_code
from .solar import _provider_worker_environment
from .analysis_call_metadata import METADATA_VERSION, MODELS, unavailable_metadata, validate_metadata
from .deepseek_evaluation import MODEL


class AnalysisProcessError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def run_analysis_process(document: str, document_id: str, key: str,
                               deadline: float, *, recoverable_solar: bool = False,
                               integrated_candidates: bool = False, nvidia_key=None,
                               nvidia_only: bool = False, command=None, call_diagnostics=None,
                               nvidia_review_model=None, contract=CONTRACT) -> dict:
    flags = (recoverable_solar, integrated_candidates, nvidia_only)
    if (any(type(flag) is not bool for flag in flags) or sum(flags) > 1
            or contract not in (CONTRACT, REVIEW_CONTRACT) or (contract == REVIEW_CONTRACT and not nvidia_only)
            or (integrated_candidates and (type(nvidia_key) is not str or not nvidia_key.strip()))
            or (nvidia_only and (type(key) is not str or not key.strip()))
            or (not integrated_candidates and nvidia_key is not None)
            or (nvidia_review_model is not None and
                (not nvidia_only or call_diagnostics is None or type(nvidia_review_model) is not str
                 or nvidia_review_model not in MODELS))
            or (call_diagnostics is not None and
                (not nvidia_only or type(call_diagnostics) is not dict or call_diagnostics))):
        raise AnalysisProcessError("ANALYSIS_WORKER_FAILED")
    if call_diagnostics is not None:
        call_diagnostics.update(unavailable_metadata('ANALYSIS_WORKER_FAILED'))
    request = {"document": document, "documentId": document_id, "key": key}
    if recoverable_solar:
        request["mode"] = "recoverable-solar"
    if integrated_candidates:
        request.update(mode='integrated-candidates', nvidiaKey=nvidia_key)
    if nvidia_only:
        request['mode'] = 'integrated-nvidia'
        if contract == REVIEW_CONTRACT:
            request['contract'] = contract
    if call_diagnostics is not None:
        request['diagnostics'] = METADATA_VERSION
    if nvidia_review_model is not None:
        request['reviewModel'] = nvidia_review_model
    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_INPUT_BYTES:
        raise AnalysisProcessError("ANALYSIS_WORKER_FAILED")
    argv = command if command is not None else [
        sys.executable, "-m", "agentfit_ai.analysis_worker"]
    process = None
    try:
        async with asyncio.timeout_at(deadline):
            process = await asyncio.create_subprocess_exec(
                *argv, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                cwd=Path(__file__).resolve().parents[1],
                env=_provider_worker_environment())
            process.stdin.write(payload)
            await process.stdin.drain()
            process.stdin.close()
            try:
                output = await process.stdout.readexactly(MAX_OUTPUT_BYTES + 1)
            except asyncio.IncompleteReadError as error:
                output = error.partial
            if len(output) > MAX_OUTPUT_BYTES:
                raise AnalysisProcessError("ANALYSIS_WORKER_FAILED")
            await process.wait()
            if process.returncode != 0:
                raise AnalysisProcessError("ANALYSIS_WORKER_FAILED")
    except TimeoutError:
        if call_diagnostics is not None:
            call_diagnostics.update(unavailable_metadata('ANALYSIS_DEADLINE_EXCEEDED'))
        raise AnalysisProcessError("ANALYSIS_DEADLINE_EXCEEDED") from None
    except OSError:
        raise AnalysisProcessError("ANALYSIS_WORKER_FAILED") from None
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
    try:
        result = json.loads(output)
    except (ValueError, UnicodeError, RecursionError):
        raise AnalysisProcessError("ANALYSIS_WORKER_FAILED") from None
    if type(result) is not dict:
        raise AnalysisProcessError("ANALYSIS_WORKER_FAILED")
    metadata = None
    if call_diagnostics is not None:
        try:
            if set(result) != {'version', 'result', 'diagnostics'} or result['version'] != METADATA_VERSION:
                raise ValueError
            metadata = validate_metadata(result['diagnostics'])
            result = result['result']
            if type(result) is not dict:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise AnalysisProcessError('ANALYSIS_WORKER_FAILED') from None

    def accept(checked):
        if metadata is not None:
            failed = checked.get('outcome') == 'failed' or set(checked) == {'error'}
            if metadata['status'] == 'unavailable' and not failed:
                raise AnalysisProcessError('ANALYSIS_WORKER_FAILED')
            if metadata['status'] == 'available' and failed != (metadata['failureStage'] is not None):
                raise AnalysisProcessError('ANALYSIS_WORKER_FAILED')
            provider_error = metadata['calls'][-1]['provider_error'] if metadata['calls'] else None
            if provider_error is not None and checked.get('error') != provider_error:
                raise AnalysisProcessError('ANALYSIS_WORKER_FAILED')
            if nvidia_review_model is not None and any(
                    row['requested_model'] != (nvidia_review_model if row['stage'] == 'COVERAGE_REVIEW_FAILED' else MODEL)
                    for row in metadata['calls']):
                raise AnalysisProcessError('ANALYSIS_WORKER_FAILED')
            call_diagnostics.update(metadata)
        return checked
    if set(result) == {"error"} and type(result["error"]) is str:
        if result["error"] == "ANALYSIS_WORKER_FAILED":
            raise AnalysisProcessError("ANALYSIS_WORKER_FAILED")
        if safe_code(result["error"]) == result["error"]:
            return accept(result)
    if integrated_candidates or nvidia_only:
        if (set(result) == {'contract', 'outcome', 'error'} and result['contract'] == contract
                and result['outcome'] == 'failed' and type(result['error']) is str
                and safe_code(result['error']) == result['error']):
            return accept(result)
        try:
            return accept(validate_candidate_confirmation(document, document_id, result, contract=contract))
        except (TypeError, ValueError, KeyError):
            raise AnalysisProcessError("ANALYSIS_WORKER_FAILED") from None
    if (set(result) == {"outcome", "profile"} and result["outcome"] == "complete"
            and type(result["profile"]) is dict):
        return result
    if (set(result) == {"outcome", "error"} and result["outcome"] == "failed"
            and type(result["error"]) is str and safe_code(result["error"]) == result["error"]
            and recoverable_solar):
        return result
    if (set(result) == {"outcome", "profile", "fieldStates", "questions", "error"}
            and result["outcome"] == "needs_confirmation" and recoverable_solar
            and type(result["profile"]) is dict and type(result["fieldStates"]) is dict
            and type(result["questions"]) is list and type(result["error"]) is str
            and safe_code(result["error"]) == result["error"]):
        return result
    raise AnalysisProcessError("ANALYSIS_WORKER_FAILED")
