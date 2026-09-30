"""Separate NVIDIA experiment; default execution only verifies local inputs."""
import argparse
import asyncio
from functools import partial
import json
import math
from pathlib import Path
import time

from .analysis_process import AnalysisProcessError, run_analysis_process
from .diagnostics import SAFE_CODES, safe_code
from .independent_evaluation_corpus import validate_gold
from .independent_evaluation_protocol import validate_score
from .independent_evaluation_runner import _failure, _identity, _read_existing, _summary, _validate_row, _write_new
from .independent_profile_evaluation import score_confirmation
from .nvidia_evaluation_inputs import MODELS, load_nvidia_key, prepare_evaluation, read_json, validate_free_access
from .analysis_call_metadata import validate_metadata, unavailable_metadata
from .deepseek_evaluation import MODEL

DIAGNOSTIC_VARIANT = 'nvidia-call-diagnostics-v1'
DEEPSEEK_REVIEW_VARIANT = 'nvidia-deepseek-review-v1'
DIAGNOSTIC_VARIANTS = (DIAGNOSTIC_VARIANT, DEEPSEEK_REVIEW_VARIANT)

STOP_CODES = frozenset(code for code in SAFE_CODES if code.startswith('PROVIDER_')) | {
    'MISSING_OR_INVALID_KEY', 'ANALYSIS_DEADLINE', 'ANALYSIS_FAILURE', 'CALL_LIMIT'}


def _validate_input(document, document_id, gold, key):
    try:
        validate_gold(document, gold)
        if (document_id != gold['case_id'] or type(key) is not str or not key or len(key) > 4096
                or key != key.strip() or any(ord(c) < 32 for c in key)
                or key in document or key in document_id):
            raise ValueError
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('INVALID_EVALUATION_INPUT') from None


async def run_scored_process(document, document_id, gold, nvidia_key, *, timeout_seconds=1800,
                             command=None, call_diagnostics=None, review_model=None):
    _validate_input(document, document_id, gold, nvidia_key)
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 1800
            or (review_model is not None and (call_diagnostics is None or type(review_model) is not str
                                             or review_model not in MODELS))
            or (call_diagnostics is not None and (type(call_diagnostics) is not dict or call_diagnostics))):
        raise ValueError('INVALID_EVALUATION_INPUT')
    try:
        options = {'call_diagnostics': call_diagnostics} if call_diagnostics is not None else {}
        if review_model is not None:
            options['nvidia_review_model'] = review_model
        outcome = await run_analysis_process(document, document_id, nvidia_key,
            asyncio.get_running_loop().time() + timeout_seconds, nvidia_only=True, command=command, **options)
        if set(outcome) == {'error'}:
            outcome = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': safe_code(outcome['error'])}
    except AnalysisProcessError as error:
        code = 'ANALYSIS_DEADLINE' if error.code == 'ANALYSIS_DEADLINE_EXCEEDED' else 'ANALYSIS_FAILURE'
        return _failure(document, document_id, gold, code)
    return validate_score(document, gold, score_confirmation(document, document_id, gold, outcome))


def _refresh(prepared):
    if (type(prepared) is not dict or set(prepared) != {'cases', 'metadata', 'paths'}
            or type(prepared['paths']) is not list or len(prepared['paths']) != 3):
        raise ValueError('INVALID_EVALUATION_PREFLIGHT')
    variant = prepared['metadata'].get('variant')
    latest = prepare_evaluation(*prepared['paths'], call_diagnostics=variant in DIAGNOSTIC_VARIANTS,
        review_model=MODEL if variant == DEEPSEEK_REVIEW_VARIANT else None)
    if latest['metadata'] != prepared['metadata']:
        raise ValueError('EXPERIMENT_CHANGED')
    return latest


def _diagnostic_row(case, identity, row, *, review_model='z-ai/glm-5.3'):
    try:
        if type(row) is not dict or 'diagnostics' not in row:
            raise ValueError
        checked = _validate_row(case, identity, {k: v for k, v in row.items() if k != 'diagnostics'})
        report = validate_metadata(row['diagnostics'])
        if report['status'] == 'available':
            if (checked['score']['status'] == 'failed') != (report['failureStage'] is not None):
                raise ValueError
        elif checked['score']['status'] != 'failed':
            raise ValueError
        provider_error = report['calls'][-1]['provider_error'] if report['calls'] else None
        if provider_error is not None and checked['score']['error'] != provider_error:
            raise ValueError
        if any(call['requested_model'] != (review_model if call['stage'] == 'COVERAGE_REVIEW_FAILED' else MODEL)
               for call in report['calls']):
            raise ValueError
        return row
    except (ValueError, TypeError, KeyError):
        raise ValueError('INVALID_CHECKPOINT') from None


async def evaluate(prepared, output, nvidia_key, access_file):
    prepared = _refresh(prepared)
    cases, metadata = prepared['cases'], prepared['metadata']
    diagnostic_mode = metadata['variant'] in DIAGNOSTIC_VARIANTS
    selected_review = MODEL if metadata['variant'] == DEEPSEEK_REVIEW_VARIANT else None
    check_row = (partial(_diagnostic_row, review_model=metadata['settings']['review_model'])
                 if diagnostic_mode else _validate_row)
    validate_free_access(access_file, reserved_calls=0)
    for case in cases:
        _validate_input(case['document'], case['case_id'], case['gold'], nvidia_key)
    output = Path(output)
    if output.is_symlink():
        raise ValueError('INVALID_CHECKPOINT')
    output.mkdir(parents=True, exist_ok=True)
    manifest = output/'experiment.json'
    if manifest.exists():
        try:
            if read_json(manifest) != metadata:
                raise ValueError
        except (ValueError, OSError, RecursionError):
            raise ValueError('EXPERIMENT_CHANGED') from None
    else:
        if any(output.iterdir()):
            raise ValueError('INVALID_CHECKPOINT')
        _write_new(manifest, metadata)
    rows = _read_existing(output, cases, metadata, row_validator=check_row)
    if any(row['score']['error'] in STOP_CODES for row in rows.values()):
        raise ValueError('EVALUATION_PROVIDER_STOPPED')
    validate_free_access(access_file, reserved_calls=len(rows)*64)
    for case in cases:
        for run in range(3):
            if (case['case_id'], run) in rows:
                continue
            _refresh(prepared)
            validate_free_access(access_file, reserved_calls=(len(rows)+1)*64)
            identity = _identity(case, run, metadata)
            stem = f'{case["case_id"]}-run-{run}'
            _write_new(output/(stem+'.started.json'), {'version': 'independent-evaluation-start-v1', **identity})
            started = time.monotonic()
            diagnostics = {} if diagnostic_mode else None
            try:
                options = {'call_diagnostics': diagnostics} if diagnostic_mode else {}
                if selected_review is not None:
                    options['review_model'] = selected_review
                score = await run_scored_process(case['document'], case['case_id'], case['gold'], nvidia_key, **options)
                score = validate_score(case['document'], case['gold'], score)
            except Exception:
                score = _failure(case['document'], case['case_id'], case['gold'], 'ANALYSIS_FAILURE')
                if diagnostic_mode:
                    diagnostics = unavailable_metadata('ANALYSIS_WORKER_FAILED')
            row = {**identity, 'elapsed_seconds': round(time.monotonic()-started, 6), 'score': score}
            if diagnostic_mode:
                row['diagnostics'] = validate_metadata(diagnostics or unavailable_metadata('NOT_RETURNED'))
            check_row(case, identity, row)
            path = output/(stem+'.json')
            _write_new(path, row)
            rows[(case['case_id'], run)] = check_row(case, identity, read_json(path))
            if score['error'] in STOP_CODES:
                raise ValueError('EVALUATION_PROVIDER_STOPPED')
    _refresh(prepared)
    rows = _read_existing(output, cases, metadata, row_validator=check_row)
    if len(rows) != 30:
        raise ValueError('INCOMPLETE_RUN')
    summary = _summary(rows)
    summary.update(version=metadata['version'].replace('-evaluation-run-', '-evaluation-summary-'),
        variant=metadata['variant'],
        reserved_model_calls_upper_bound=len(rows)*64, baseline_status='incomplete', new_holdout=False)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description='Preflight fixed NVIDIA evaluation; live requires confirmed free scope.')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--call-diagnostics', action='store_true')
    parser.add_argument('--review-model', choices=sorted(MODELS))
    for name in ('corpus', 'gold', 'freeze'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('env-file', 'output', 'access-confirmation'):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args(argv)
    try:
        prepared = prepare_evaluation(args.corpus, args.gold, args.freeze,
            call_diagnostics=args.call_diagnostics, review_model=args.review_model)
        if not args.live:
            summary = {'mode': 'preflight', 'cases': len(prepared['cases']), 'expected': 30,
                'gold_units': sum(len(f['units']) for c in prepared['cases'] for f in c['gold']['fields'].values()),
                'metadata': prepared['metadata'], 'release_gate_passed': False}
        else:
            validate_free_access(args.access_confirmation, reserved_calls=64)
            if args.env_file is None or args.output is None:
                raise ValueError('INVALID_EVALUATION_INPUT')
            key = load_nvidia_key(args.env_file)
            summary = asyncio.run(evaluate(prepared, args.output, key, args.access_confirmation))
    except KeyboardInterrupt:
        print(json.dumps({'error': 'EVALUATION_INTERRUPTED'}))
        return 1
    except Exception as error:
        allowed = {'INVALID_EVALUATION_PREFLIGHT', 'INVALID_EVALUATION_KEYS', 'INVALID_EVALUATION_INPUT',
            'INVALID_CHECKPOINT', 'INCOMPLETE_RUN', 'EXPERIMENT_CHANGED', 'FREE_ACCESS_UNCONFIRMED',
            'FREE_ACCESS_BUDGET_EXHAUSTED', 'EVALUATION_PROVIDER_STOPPED'}
        code = str(error) if type(error) is ValueError and str(error) in allowed else 'EVALUATION_FAILED'
        print(json.dumps({'error': code}))
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
