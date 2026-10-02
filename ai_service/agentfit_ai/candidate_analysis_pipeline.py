"""Opt-in integration of source candidates, semantic review and feature curation."""

from copy import deepcopy
from functools import partial
from time import monotonic, sleep

from .candidate_first_profile import (
    CandidateContractError, CandidatePipelineError, apply_candidate_review,
    classify_profile_candidates, extract_profile_candidates, finalize_candidate_analysis,
    freeze_candidate_occurrences,
)
from .candidate_feature_curation import curate_reviewed_features
from .candidate_field_review import review_candidates_by_field
from .capability_candidates import extract_capability_candidates
from .candidate_split_review import review_candidates_separately
from .candidate_semantic_assessment import classify_grounded_candidates
from .semantic_confirmation_metadata import unresolved_decision_fields
from .deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS
from .diagnostics import safe_code
from .nvidia_streaming import post_nvidia_streaming
from .operation_candidates import _validate_frozen, extract_operation_candidates
from .solar import AnalysisError, _reject_sensitive, post_solar


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
                                  max_calls=64, nvidia_retry_limit=1, candidate_model=None,
                                  capability_candidates=False, field_local_review=False,
                                  classification_model=None, classification_batch_size=30,
                                  semantic_assessment=False, detail_observer=None):
    """Run fresh extraction through reviewed projection with one provider-call budget.

    Injected extractors are trusted callbacks. Only the default LangExtract adapter's
    network activity is routed through the shared meter.
    """
    nvidia_only = candidate_model is not None
    if nvidia_only and (type(candidate_model) is not str or candidate_model not in NVIDIA_REVIEW_MODELS
                        or solar_key is not None or solar_transport is not None or nvidia_retry_limit != 0):
        raise ValueError('invalid NVIDIA-only candidate options')
    keys = (nvidia_key,) if nvidia_only else (solar_key, nvidia_key)
    if (type(document) is not str or not document.strip() or len(document) > 100_000 or
            type(document_id) is not str or not document_id.strip() or
            any(type(key) is not str or not key.strip() for key in keys)):
        raise ValueError('invalid integrated analysis input')
    if (any(key in document or key in document_id for key in keys) or
            any(type(model) is not str or model not in NVIDIA_REVIEW_MODELS
                for model in (review_model, feature_model)) or
            any(callback is not None and not callable(callback)
                for callback in (extractor, solar_transport, nvidia_transport, observer, detail_observer)) or
            any(collector is not None and type(collector) is not list
                for collector in (call_trace, review_calls)) or
            type(max_calls) is not int or not 1 <= max_calls <= 64 or
            type(nvidia_retry_limit) is not int or nvidia_retry_limit not in (0, 1) or
            type(capability_candidates) is not bool or type(field_local_review) is not bool or
            type(semantic_assessment) is not bool or (semantic_assessment and not nvidia_only) or
            (classification_model is not None and
             (type(classification_model) is not str or classification_model not in NVIDIA_REVIEW_MODELS)) or
            type(classification_batch_size) is not int or classification_batch_size not in (15, 30)):
        raise ValueError('invalid integrated analysis options')

    candidate_key = nvidia_key if nvidia_only else solar_key
    _reject_sensitive(document, candidate_key)
    _reject_sensitive(document_id, candidate_key)

    current_stage, call_count, budget_exceeded = None, 0, False
    stopped_provider_code = None

    def run(stage, operation):
        nonlocal current_stage
        current_stage = stage
        try:
            result = operation()
        except Exception as error:
            if budget_exceeded:
                raise CandidatePipelineError(stage, detail='CALL_BUDGET_EXCEEDED') from None
            if stopped_provider_code is not None:
                raise CandidatePipelineError(stage, stopped_provider_code) from None
            # The finalizer already isolates observer failures from projection failures.
            if stage == 'PROJECTION_FAILED' and isinstance(error, CandidatePipelineError):
                raise error from None
            code = safe_code(error.code) if isinstance(error, AnalysisError) else None
            detail = (error.code if isinstance(error, CandidateContractError)
                      and error.code in _CONTRACT_DETAILS else None)
            raise CandidatePipelineError(stage, code, detail) from None
        if budget_exceeded:  # A third-party extractor may catch transport exceptions.
            raise CandidatePipelineError(stage, detail='CALL_BUDGET_EXCEEDED') from None
        if stopped_provider_code is not None:
            raise CandidatePipelineError(stage, stopped_provider_code) from None
        return result

    def observe(stage, state):
        if observer is not None:
            run('DIAGNOSTIC_FAILED', lambda: observer(stage, deepcopy(state)))

    def detail(stage, state):
        if detail_observer is not None:
            # Keep the established four-stage observer contract unchanged.
            run('DIAGNOSTIC_FAILED', lambda: detail_observer(stage, deepcopy(state)))

    def metered(provider, transport):
        def send(payload, key, timeout):
            nonlocal call_count, budget_exceeded, stopped_provider_code
            if stopped_provider_code is not None:
                raise AnalysisError(stopped_provider_code)
            original = deepcopy(payload) if provider == 'nvidia' else payload
            requested = original.get('model')
            allowed = ('solar-pro4',) if provider == 'solar' else NVIDIA_REVIEW_MODELS
            attempts = 1 + (nvidia_retry_limit if provider == 'nvidia' else 0)
            first_index = call_count + 1
            for attempt in range(1, attempts + 1):
                if call_count >= max_calls:
                    budget_exceeded = True
                    raise AnalysisError('PROVIDER_FAILURE')
                call_count += 1
                row = {'stage': current_stage, 'provider': provider,
                       'requested_model': requested if type(requested) is str and requested in allowed else None,
                       'call_index': call_count, 'elapsed_ms': 0, 'response_bytes': None,
                       'transport_completed': False, 'attempt': attempt,
                       'retry_of_call_index': first_index if attempt > 1 else None,
                       'provider_error': None}
                started = monotonic()
                try:
                    outgoing = deepcopy(original) if provider == 'nvidia' else original
                    raw = transport(outgoing, key, timeout)
                    row['transport_completed'] = type(raw) is bytes
                    row['response_bytes'] = len(raw) if type(raw) is bytes else None
                    return raw
                except AnalysisError as error:
                    row['provider_error'] = safe_code(error.code)
                    if nvidia_only:
                        stopped_provider_code = row['provider_error']
                        raise
                    if error.code != 'PROVIDER_UNAVAILABLE' or attempt >= attempts:
                        raise
                    if call_count >= max_calls:
                        budget_exceeded = True
                        raise AnalysisError('PROVIDER_FAILURE') from None
                except Exception:
                    if nvidia_only:
                        stopped_provider_code = row['provider_error'] = 'PROVIDER_FAILURE'
                        raise AnalysisError('PROVIDER_FAILURE') from None
                    raise
                finally:
                    row['elapsed_ms'] = round((monotonic() - started) * 1000)
                    if call_trace is not None:
                        call_trace.append(row)
                sleep(2.0)
        return send

    solar_send = metered('solar', solar_transport or post_solar)
    nvidia_send = metered('nvidia', post_nvidia_streaming if nvidia_transport is None else nvidia_transport)
    candidate_send = nvidia_send if nvidia_only else solar_send
    candidate_options = {'nvidia_model': candidate_model} if nvidia_only else {}
    classification_key, classification_send = candidate_key, candidate_send
    classification_options = candidate_options
    if classification_model is not None:
        classification_key, classification_send = nvidia_key, nvidia_send
        classification_options = {'nvidia_model': classification_model}

    def extract():
        selected = extractor
        if selected is None:
            from .langextract_solar_trial import extract_candidates
            selected = partial(extract_candidates, transport=candidate_send, **candidate_options)
        return extract_profile_candidates(document, candidate_key, extractor=selected)

    extractions = run('EXTRACTION_FAILED', extract)
    detail('general_extracted', extractions)
    general = run('GROUNDING_FAILED', lambda: freeze_candidate_occurrences(document, extractions))
    detail('general_grounded', general)
    operation_extractor = extract_capability_candidates if capability_candidates else extract_operation_candidates
    operations = run('OPERATION_EXTRACTION_FAILED', lambda: operation_extractor(
        document, nvidia_key, model=feature_model, transport=nvidia_send))
    detail('operations_grounded', operations)
    detail('grounding_inputs', {'general': general, 'operations': operations})
    frozen = run('MERGE_FAILED', lambda: _merge_occurrences(document, general, operations))
    observe('grounded', frozen)
    decisions = None
    if semantic_assessment:
        assessed = run('CLASSIFICATION_FAILED', lambda: classify_grounded_candidates(
            document, frozen, classification_key, transport=classification_send,
            model=classification_model or candidate_model))
        labels, decisions = assessed['labels'], assessed['modelDecisions']
        detail('semantic_assessed', assessed)
    else:
        labels = run('CLASSIFICATION_FAILED', lambda: classify_profile_candidates(
            document, frozen, classification_key, transport=classification_send,
            field_semantics='explicit-v1', batch_size=classification_batch_size,
            **classification_options))
    observe('classified', {'frozen': frozen, 'labels': labels})
    reviewer = review_candidates_by_field if field_local_review else review_candidates_separately
    review_options = {} if field_local_review else {
        'reasoned_review': True, 'adaptive_review': False, 'field_semantics': 'explicit-v1'}
    review = run('COVERAGE_REVIEW_FAILED', lambda: reviewer(
        document, frozen, labels, nvidia_key, transport=nvidia_send,
        review_model=review_model, review_calls=review_calls, **review_options))
    safe_labels = run('COVERAGE_REVIEW_FAILED', lambda: apply_candidate_review(frozen, labels, review))
    detail('review_completed', {'frozen': frozen, 'labels': safe_labels, 'review': review})
    curation = run('FEATURE_CURATION_FAILED', lambda: curate_reviewed_features(
        document, frozen, safe_labels, nvidia_key, model=feature_model, transport=nvidia_send))
    detail('feature_curated', {'frozen': frozen, 'labels': safe_labels, 'curation': curation})
    result = run('PROJECTION_FAILED', lambda: finalize_candidate_analysis(
        document, document_id, frozen, labels, review,
        observer=observe if observer is not None else None, feature_curation=curation))
    if decisions is not None:
        result['modelDecisions'] = decisions
        unresolved = set(result['unresolvedFields']) | unresolved_decision_fields(decisions)
        result['unresolvedFields'] = [f for f in review['checkedFields'] if f in unresolved]
        result['reviewIssueCount'] += sum(r['decision'] == 'needs_confirmation' for r in decisions)
        if unresolved or result['reviewIssueCount']:
            result['outcome'] = 'needs_confirmation'
    return result


def analyze_nvidia_candidates(document, document_id, nvidia_key, *,
                              candidate_model=MODEL, review_model='z-ai/glm-5.3', feature_model=MODEL,
                              nvidia_transport=None, observer=None, call_trace=None,
                              review_calls=None, max_calls=64, capability_candidates=False,
                              field_local_review=False, classification_model=None,
                              classification_batch_size=30, semantic_assessment=False, detail_observer=None):
    """Opt-in NVIDIA-only variant; no retries, fallback, or account/billing guarantee.

    Callers own the total process deadline and must establish permission and free
    account capacity before using the default external transport.
    """
    if type(candidate_model) is not str or candidate_model not in NVIDIA_REVIEW_MODELS:
        raise ValueError('unsupported NVIDIA candidate model')
    return analyze_integrated_candidates(
        document, document_id, None, nvidia_key, candidate_model=candidate_model,
        review_model=review_model, feature_model=feature_model,
        nvidia_transport=nvidia_transport, observer=observer,
        call_trace=call_trace, review_calls=review_calls, max_calls=max_calls,
        nvidia_retry_limit=0, capability_candidates=capability_candidates,
        field_local_review=field_local_review, classification_model=classification_model,
        classification_batch_size=classification_batch_size, semantic_assessment=semantic_assessment,
        detail_observer=detail_observer)
