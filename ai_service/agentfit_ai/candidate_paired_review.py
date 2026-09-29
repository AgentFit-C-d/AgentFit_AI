"""Opt-in same-input reviewer comparison; source and model responses stay in memory."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import time

from .candidate_first_profile import (
    CandidatePipelineError, classify_profile_candidates, extract_profile_candidates,
    finalize_candidate_analysis, freeze_candidate_occurrences, validate_candidate_labels,
)
from .candidate_split_review import _payload, review_candidates_separately
from .candidate_stage_diagnostics import CandidateStageDiagnostics
from .deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS, load_key as load_nvidia_key, nvidia_payload
from .diagnostics import safe_code
from .false_complete_evaluation import write_safe_json
from .langextract_solar_trial import load_key as load_solar_key
from .profile import ARRAY_FIELDS, FIELDS, MAX_ARRAY_ITEMS, MAX_TEXT_CODE_POINTS
from .real_document_holdout import prepare_cases, score_profile, select_cases
from .solar import AnalysisError


REVIEW_MODELS = ('solar-pro4', *NVIDIA_REVIEW_MODELS)


def _review_settings(models):
    source = _payload('settings', '', {}, {})
    settings = {}
    for model in models:
        payload = source if model == 'solar-pro4' else nvidia_payload(source, model=model)
        settings[model] = {name: payload[name] for name in (
            'temperature', 'reasoning_effort', 'chat_template_kwargs', 'max_tokens') if name in payload}
        settings[model].update(timeout_seconds=600, candidate_batch_size=20,
                               adaptive_review=model == 'solar-pro4')
    return settings


def _references(frozen, labels):
    by_id = {label['id']: label for label in labels}
    return [{**item, 'field': by_id[item['id']]['field'],
             'status': by_id[item['id']]['status']} for item in frozen['candidates']]


def _field_summaries(document, frozen, before, after, profile):
    spans = {item['id']: item for item in frozen['candidates']}
    result = {}
    for field in FIELDS:
        original = [label for label in before if label['field'] == field and
                    label['status'] == 'confirmed']
        kept = [label for label in after if label['field'] == field and
                label['status'] == 'confirmed']
        values = {document[spans[item['id']]['start']:spans[item['id']]['end']]
                  for item in kept}
        oversized = sum(len(value) > MAX_TEXT_CODE_POINTS for value in values)
        reason = ('oversized_value' if oversized else
                  'multiple_scalar_values' if field not in ARRAY_FIELDS and len(values) > 1 else
                  'array_limit' if field in ARRAY_FIELDS and len(values) > MAX_ARRAY_ITEMS else
                  'retained' if values else 'empty')
        result[field] = {'confirmed_before': len(original), 'confirmed_after': len(kept),
                         'unique_after': len(values), 'oversized_count': oversized,
                         'projected_null': profile['data'][field] is None,
                         'projection_reason': reason}
    return result


def _failure(error, stage):
    result = {'outcome': 'failed', 'error': stage}
    if isinstance(error, AnalysisError):
        result['provider_error'] = safe_code(error.code)
    elif isinstance(error, CandidatePipelineError):
        result['error'] = error.stage
        if error.provider_code:
            result['provider_error'] = safe_code(error.provider_code)
    return result


def evaluate_paired(case, solar_key, nvidia_key, models, *, extractor=None,
                    classifier=None, reviewer=None, on_update=None):
    """Prepare once; each reviewer receives an isolated copy and its own key."""
    if (type(models) not in (list, tuple) or not 1 <= len(models) <= len(REVIEW_MODELS) or
            any(type(model) is not str or model not in REVIEW_MODELS for model in models) or
            len(set(models)) != len(models)):
        raise ValueError('invalid review model selection')
    if any(type(key) is not str or not key.strip() for key in (solar_key, nvidia_key)):
        raise ValueError('missing provider key')
    if on_update is not None and not callable(on_update):
        raise ValueError('invalid progress observer')
    # Validate gold before any provider call, but never send it to a provider.
    diagnostic = CandidateStageDiagnostics(case.text, case.checks)
    result = {'case_id': case.id, 'source_sha256': case.source_sha256,
              'redacted_sha256': case.redacted_sha256, 'total_models': len(models),
              'state': 'running', 'models': [], 'failed': 0,
              'model_order': list(models), 'held_out': False,
              'review_settings': _review_settings(models)}

    def emit():
        result['failed'] = sum(row['outcome'] == 'failed' for row in result['models'])
        if on_update:
            on_update(deepcopy(result))

    stage = 'EXTRACTION_FAILED'
    started = time.monotonic()
    try:
        if any(key in case.text or key in case.id for key in (solar_key, nvidia_key)):
            if any(key in case.id for key in (solar_key, nvidia_key)):
                result['case_id'] = 'redacted'
            stage = 'SENSITIVE_CONTENT'
            raise AnalysisError('SENSITIVE_CONTENT')
        extractions = extract_profile_candidates(case.text, solar_key, extractor=extractor)
        stage = 'GROUNDING_FAILED'
        frozen = freeze_candidate_occurrences(case.text, extractions)
        diagnostic.observe('grounded', frozen)
        stage = 'CLASSIFICATION_FAILED'
        classify = classifier or classify_profile_candidates
        labels = classify(case.text, deepcopy(frozen), solar_key)
        validate_candidate_labels(frozen, labels)
        diagnostic.observe('classified', {'frozen': frozen, 'labels': labels})
    except Exception as error:
        result['common_error'] = stage
        result['models'] = [{'review_model': model, **_failure(error, stage)} for model in models]
        result['upstream_elapsed_ms'] = round((time.monotonic() - started) * 1000)
        result['state'] = 'finished'
        emit()
        return result
    result.update(upstream_elapsed_ms=round((time.monotonic() - started) * 1000),
                  candidate_count=len(frozen['candidates']),
                  rejected_candidate_count=len(frozen['rejected']),
                  classification_refs=_references(frozen, labels))
    emit()
    review = reviewer or review_candidates_separately
    for index, model in enumerate(models):
        calls = []
        row = {'review_model': model, 'review_calls': calls}
        arm_diagnostic = deepcopy(diagnostic)
        reviewed = {}
        def observer(stage, state):
            arm_diagnostic.observe(stage, state)
            if stage == 'reviewed':
                reviewed.update(state)
        started = time.monotonic()
        stage = 'COVERAGE_REVIEW_FAILED'
        try:
            verdict = review(case.text, deepcopy(frozen), deepcopy(labels),
                solar_key if model == 'solar-pro4' else nvidia_key,
                review_model=model, review_calls=calls, adaptive_review=True)
            stage = 'PROJECTION_FAILED'
            projected = finalize_candidate_analysis(case.text, case.id, frozen, labels,
                                                     verdict, observer=observer)
            row.update(outcome=projected['outcome'],
                       unresolved_fields=projected['unresolvedFields'],
                       review_issue_count=projected['reviewIssueCount'],
                       reviewed_refs=_references(frozen, reviewed['labels']),
                       fields=_field_summaries(case.text, frozen, labels, reviewed['labels'],
                                               projected['profile']))
            score = score_profile(projected['profile'], case.checks)
            if projected['outcome'] == 'candidate_profile':
                row.update(score)
            else:
                row.update(suggestion_matched=score['matched'], suggestion_checked=score['total'],
                           suggestion_failed_check_ids=score['failed_check_ids'])
        except Exception as error:
            row.update(_failure(error, stage))
        row['stage_checks'] = arm_diagnostic.summary()
        row['review_elapsed_ms'] = round((time.monotonic() - started) * 1000)
        result['models'].append(row)
        if index == len(models) - 1:
            result['state'] = 'finished'
        emit()
    return result


def main():
    parser = argparse.ArgumentParser(description='Same-candidate Solar/NVIDIA review comparison')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--case-id', choices=('H01', 'H02', 'H03'), required=True)
    parser.add_argument('--review-model', choices=REVIEW_MODELS, action='append')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live required')
    if args.output.exists():
        parser.error('output already exists')
    models = args.review_model or ['solar-pro4', MODEL]
    if len(set(models)) != len(models):
        parser.error('duplicate review models')
    try:
        manifest = args.manifest.read_bytes().replace(b'\r\n', b'\n')
        if (re.fullmatch(r'[0-9a-f]{64}', args.manifest_sha256) is None or
                hashlib.sha256(manifest).hexdigest() != args.manifest_sha256):
            raise ValueError('manifest hash mismatch')
        payload = json.loads(manifest.decode('utf-8'))
        if type(payload) is not dict or set(payload) != {'cases'}:
            raise ValueError('invalid manifest')
        prepared = prepare_cases(payload['cases'])
        case = select_cases(prepared, args.case_id)[0]
    except Exception:
        parser.error('private document preflight failed')
    try:
        solar_key = load_solar_key(args.env_file)
        nvidia_key = load_nvidia_key(args.env_file)
    except ValueError:
        parser.error('provider key configuration missing')
    forbidden = (solar_key, nvidia_key, *(item.text for item in prepared),
                 *(str(item.get('path', '')) for item in payload['cases']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def persist(result):
        write_safe_json(args.output, result, forbidden_strings=forbidden)
    result = evaluate_paired(case, solar_key, nvidia_key, models, on_update=persist)
    print(json.dumps({'state': result['state'], 'total_models': result['total_models'],
                      'failed': result['failed'], 'outcomes': [row['outcome'] for row in result['models']]}))
    return 0 if result['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
