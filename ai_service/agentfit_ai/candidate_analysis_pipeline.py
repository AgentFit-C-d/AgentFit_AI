"""Opt-in integration of source candidates, semantic review and feature curation."""

from copy import deepcopy
from functools import partial
from time import monotonic

from .candidate_first_profile import (
    CandidateContractError, CandidatePipelineError, apply_candidate_review,
    classify_profile_candidates, extract_profile_candidates, finalize_candidate_analysis,
    freeze_candidate_occurrences,
)
from .candidate_feature_curation import curate_reviewed_features
from .candidate_split_review import review_candidates_separately
from .deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS, post_nvidia
from .diagnostics import safe_code
from .operation_candidates import _validate_frozen, extract_operation_candidates
from .solar import AnalysisError, post_solar


_CONTRACT_DETAILS = frozenset((
    'CANDIDATE_OCCURRENCE_LIMIT', 'INVALID_CANDIDATE_SET', 'DUPLICATE_CANDIDATE_ID',
    'LABEL_COUNT_MISMATCH', 'INVALID_LABEL', 'OTHER_STATUS_INVALID', 'LABEL_ID_MISMATCH',
))


def _merge_occurrences(document, *sets):
    """Merge unclassified spans; certainty is decided once after deduplication."""
    if not sets:
        raise ValueError('missing candidate sets')
    positions, rejected = set(), []
    for frozen in sets:
        _validate_frozen(document, frozen)
        positions.update((item['start'], item['end']) for item in frozen['candidates'])
        if len(positions) > 240:
            raise CandidateContractError('CANDIDATE_OCCURRENCE_LIMIT')
        for item in frozen['rejected']:
            rejected.append({'index': len(rejected), 'reason': item['reason']})
    return {'candidates': [{'id': f'C{index:03}', 'start': start, 'end': end}
                           for index, (start, end) in enumerate(sorted(positions))],
            'rejected': rejected}


def analyze_integrated_candidates(document, document_id, solar_key, nvidia_key, *,
                                  review_model='z-ai/glm-5.3', feature_model=MODEL,
                                  extractor=None, solar_transport=None, nvidia_transport=None,
                                  observer=None, call_trace=None, review_calls=None,
                                  max_calls=64):
    """Run fresh extraction through reviewed projection with one provider-call budget.

    Injected extractors are trusted callbacks. Only the default LangExtract adapter's
    network activity is routed through the shared meter.
    """
    if (type(document) is not str or not document.strip() or len(document) > 100_000 or
            type(document_id) is not str or not document_id.strip() or
            any(type(key) is not str or not key.strip() for key in (solar_key, nvidia_key))):
        raise ValueError('invalid integrated analysis input')
    if (any(key in document or key in document_id for key in (solar_key, nvidia_key)) or
            any(type(model) is not str or model not in NVIDIA_REVIEW_MODELS
                for model in (review_model, feature_model)) or
            any(callback is not None and not callable(callback)
                for callback in (extractor, solar_transport, nvidia_transport, observer)) or
            any(collector is not None and type(collector) is not list
                for collector in (call_trace, review_calls)) or
            type(max_calls) is not int or not 1 <= max_calls <= 64):
        raise ValueError('invalid integrated analysis options')

    current_stage, call_count, budget_exceeded = None, 0, False

    def run(stage, operation):
        nonlocal current_stage
        current_stage = stage
        try:
            result = operation()
        except Exception as error:
            if budget_exceeded:
                raise CandidatePipelineError(stage, detail='CALL_BUDGET_EXCEEDED') from None
            # The finalizer already isolates observer failures from projection failures.
            if stage == 'PROJECTION_FAILED' and isinstance(error, CandidatePipelineError):
                raise error from None
            code = safe_code(error.code) if isinstance(error, AnalysisError) else None
            detail = (error.code if isinstance(error, CandidateContractError)
                      and error.code in _CONTRACT_DETAILS else None)
            raise CandidatePipelineError(stage, code, detail) from None
        if budget_exceeded:  # A third-party extractor may catch transport exceptions.
            raise CandidatePipelineError(stage, detail='CALL_BUDGET_EXCEEDED') from None
        return result

    def observe(stage, state):
        if observer is not None:
            run('DIAGNOSTIC_FAILED', lambda: observer(stage, deepcopy(state)))

    def metered(provider, transport):
        def send(payload, key, timeout):
            nonlocal call_count, budget_exceeded
            if call_count >= max_calls:
                budget_exceeded = True
                raise AnalysisError('PROVIDER_FAILURE')
            call_count += 1
            requested = payload.get('model')
            allowed = ('solar-pro4',) if provider == 'solar' else NVIDIA_REVIEW_MODELS
            row = {'stage': current_stage, 'provider': provider,
                   'requested_model': requested if type(requested) is str and requested in allowed else None,
                   'call_index': call_count, 'elapsed_ms': 0, 'response_bytes': None,
                   'transport_completed': False}
            started = monotonic()
            try:
                raw = transport(payload, key, timeout)
                row['transport_completed'] = type(raw) is bytes
                row['response_bytes'] = len(raw) if type(raw) is bytes else None
                return raw
            finally:
                row['elapsed_ms'] = round((monotonic() - started) * 1000)
                if call_trace is not None:
                    call_trace.append(row)
        return send

    solar_send = metered('solar', solar_transport or post_solar)
    nvidia_send = metered('nvidia', nvidia_transport or post_nvidia)

    def extract():
        selected = extractor
        if selected is None:
            from .langextract_solar_trial import extract_candidates
            selected = partial(extract_candidates, transport=solar_send)
        return extract_profile_candidates(document, solar_key, extractor=selected)

    extractions = run('EXTRACTION_FAILED', extract)
    general = run('GROUNDING_FAILED', lambda: freeze_candidate_occurrences(document, extractions))
    operations = run('OPERATION_EXTRACTION_FAILED', lambda: extract_operation_candidates(
        document, nvidia_key, model=feature_model, transport=nvidia_send))
    frozen = run('MERGE_FAILED', lambda: _merge_occurrences(document, general, operations))
    observe('grounded', frozen)
    labels = run('CLASSIFICATION_FAILED', lambda: classify_profile_candidates(
        document, frozen, solar_key, transport=solar_send, field_semantics='explicit-v1'))
    observe('classified', {'frozen': frozen, 'labels': labels})
    review = run('COVERAGE_REVIEW_FAILED', lambda: review_candidates_separately(
        document, frozen, labels, nvidia_key, transport=nvidia_send,
        review_model=review_model, reasoned_review=True, adaptive_review=False,
        field_semantics='explicit-v1', review_calls=review_calls))
    safe_labels = run('COVERAGE_REVIEW_FAILED', lambda: apply_candidate_review(frozen, labels, review))
    curation = run('FEATURE_CURATION_FAILED', lambda: curate_reviewed_features(
        document, frozen, safe_labels, nvidia_key, model=feature_model, transport=nvidia_send))
    return run('PROJECTION_FAILED', lambda: finalize_candidate_analysis(
        document, document_id, frozen, labels, review,
        observer=observe if observer is not None else None, feature_curation=curation))
