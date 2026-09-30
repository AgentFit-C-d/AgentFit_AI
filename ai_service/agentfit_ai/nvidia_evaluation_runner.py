"""Separate NVIDIA experiment; default execution only verifies local inputs."""
import argparse
import asyncio
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
from .nvidia_evaluation_inputs import load_nvidia_key, prepare_evaluation, read_json, validate_free_access

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


async def run_scored_process(document, document_id, gold, nvidia_key, *, timeout_seconds=1800, command=None):
    _validate_input(document, document_id, gold, nvidia_key)
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 1800):
        raise ValueError('INVALID_EVALUATION_INPUT')
    try:
        outcome = await run_analysis_process(document, document_id, nvidia_key,
            asyncio.get_running_loop().time() + timeout_seconds, nvidia_only=True, command=command)
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
    latest = prepare_evaluation(*prepared['paths'])
    if latest['metadata'] != prepared['metadata']:
        raise ValueError('EXPERIMENT_CHANGED')
    return latest


async def evaluate(prepared, output, nvidia_key, access_file):
    prepared = _refresh(prepared)
    cases, metadata = prepared['cases'], prepared['metadata']
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
    rows = _read_existing(output, cases, metadata)
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
            try:
                score = await run_scored_process(case['document'], case['case_id'], case['gold'], nvidia_key)
                score = validate_score(case['document'], case['gold'], score)
            except Exception:
                score = _failure(case['document'], case['case_id'], case['gold'], 'ANALYSIS_FAILURE')
            row = {**identity, 'elapsed_seconds': round(time.monotonic()-started, 6), 'score': score}
            _validate_row(case, identity, row)
            path = output/(stem+'.json')
            _write_new(path, row)
            rows[(case['case_id'], run)] = _validate_row(case, identity, read_json(path))
            if score['error'] in STOP_CODES:
                raise ValueError('EVALUATION_PROVIDER_STOPPED')
    _refresh(prepared)
    rows = _read_existing(output, cases, metadata)
    if len(rows) != 30:
        raise ValueError('INCOMPLETE_RUN')
    summary = _summary(rows)
    summary.update(version='nvidia-only-evaluation-summary-v1', variant='nvidia-only-v1',
        reserved_model_calls_upper_bound=len(rows)*64, baseline_status='incomplete', new_holdout=False)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description='Preflight fixed NVIDIA evaluation; live requires confirmed free scope.')
    parser.add_argument('--live', action='store_true')
    for name in ('corpus', 'gold', 'freeze'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('env-file', 'output', 'access-confirmation'):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args(argv)
    try:
        prepared = prepare_evaluation(args.corpus, args.gold, args.freeze)
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
