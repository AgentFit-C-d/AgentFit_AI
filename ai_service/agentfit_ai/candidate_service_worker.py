"""Integrated candidate analysis owned by one disposable request process."""

from importlib.util import find_spec

from .candidate_analysis_pipeline import analyze_integrated_candidates, analyze_nvidia_candidates
from .candidate_confirmation import CONTRACT, project_candidate_confirmation
from .candidate_first_profile import CandidatePipelineError
from .diagnostics import PIPELINE_FAILURE_CODES, safe_code
from .nvidia_streaming import post_nvidia_streaming_inline
from .solar import AnalysisError, _reject_sensitive, post_solar_inline
from .analysis_call_metadata import MODELS, build_metadata


def execute_integrated_analysis(document, document_id, solar_key, nvidia_key):
    return _execute_analysis(document, document_id, (solar_key, nvidia_key), lambda:
        analyze_integrated_candidates(document, document_id, solar_key, nvidia_key,
            solar_transport=post_solar_inline, nvidia_transport=post_nvidia_streaming_inline))


def execute_nvidia_analysis(document, document_id, nvidia_key, *, call_diagnostics=None, review_model=None,
                            semantic_assessment=False):
    if type(semantic_assessment) is not bool:
        raise ValueError('invalid semantic assessment option')
    if review_model is not None and (call_diagnostics is None or type(review_model) is not str
                                     or review_model not in MODELS):
        raise ValueError('invalid diagnostic review model')
    trace = [] if call_diagnostics is not None else None
    options = {'call_trace': trace} if trace is not None else {}
    if review_model is not None:
        options['review_model'] = review_model
    if semantic_assessment:
        options['semantic_assessment'] = True
    return _execute_analysis(document, document_id, (nvidia_key,), lambda:
        analyze_nvidia_candidates(document, document_id, nvidia_key,
            nvidia_transport=post_nvidia_streaming_inline, **options),
        call_diagnostics=call_diagnostics, call_trace=trace)


def _execute_analysis(document, document_id, keys, analyze, *, call_diagnostics=None, call_trace=None):
    for key in keys:
        if type(key) is not str or not key.strip():
            raise AnalysisError('MISSING_OR_INVALID_KEY')
        _reject_sensitive(document, key)
        _reject_sensitive(document_id, key)
    if find_spec('langextract') is None:
        raise AnalysisError('INTEGRATED_RUNTIME_UNAVAILABLE')
    try:
        result = analyze()
    except CandidatePipelineError as error:
        code = 'CALL_LIMIT' if error.detail == 'CALL_BUDGET_EXCEEDED' else safe_code(error.provider_code)
        if (code == 'ANALYSIS_FAILURE' and type(error.stage) is str
                and error.stage in PIPELINE_FAILURE_CODES):
            code = error.stage
        if call_diagnostics is not None:
            call_diagnostics.update(build_metadata(call_trace, error.stage))
        return {'contract': CONTRACT, 'outcome': 'failed', 'error': code}
    output = project_candidate_confirmation(document, document_id, result)
    if call_diagnostics is not None:
        call_diagnostics.update(build_metadata(call_trace))
    return output
