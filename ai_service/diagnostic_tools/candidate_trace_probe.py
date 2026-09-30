"""Three immutable public-document probes; default CLI is offline preflight."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from time import monotonic

from agentfit_ai.independent_evaluation_inputs import digest_json, read_bytes, read_json
from agentfit_ai.independent_evaluation_runner import _identity, _write_new
from agentfit_ai.nvidia_evaluation_inputs import load_nvidia_key, prepare_evaluation, validate_free_access
from agentfit_ai.nvidia_evaluation_runner import STOP_CODES, _diagnostic_row, _validate_input, run_scored_process
from .candidate_trace import MAX_TRACE_BYTES
from .candidate_trace_worker import MODEL, validate_probe_report

TOOLS = Path(__file__).resolve().parent
CASES = ('PUBLIC-01', 'PUBLIC-09', 'PUBLIC-07')
MAX_SECONDS = 5400
ERROR_CODES = {'INVALID_EVALUATION_PREFLIGHT', 'INVALID_EVALUATION_KEYS', 'INVALID_EVALUATION_INPUT',
    'INVALID_CHECKPOINT', 'EXPERIMENT_CHANGED', 'FREE_ACCESS_UNCONFIRMED', 'FREE_ACCESS_BUDGET_EXHAUSTED',
    'EVALUATION_PROVIDER_STOPPED', 'PROBE_BUDGET_EXHAUSTED', 'PROBE_OBSERVATION_UNAVAILABLE'}


def _tool_hashes():
    paths = sorted(TOOLS.rglob('*.py'))
    if not paths or any(p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(TOOLS.resolve())
                        for p in paths):
        raise ValueError('INVALID_EVALUATION_PREFLIGHT')
    return {p.relative_to(TOOLS).as_posix(): hashlib.sha256(
        read_bytes(p).replace(b'\r\n', b'\n')).hexdigest() for p in paths}


def prepare_probe(corpus_file, gold_file, freeze_file) -> dict:
    baseline = prepare_evaluation(corpus_file, gold_file, freeze_file,
                                  call_diagnostics=True, review_model=MODEL)
    files = _tool_hashes()
    by_id = {case['case_id']: case for case in baseline['metadata']['cases']}
    metadata = {'version': 'candidate-provenance-probe-v1', 'baseline_metadata': baseline['metadata'],
        'tool_files': files, 'tool_sha256': digest_json(files),
        'cases': [by_id[ident] for ident in CASES], 'runs_per_case': 1,
        'settings': {'request_timeout_seconds': 1800, 'max_calls_per_request': 64,
                     'max_total_reserved_calls': 192, 'max_total_seconds': MAX_SECONDS, 'retry_limit': 0},
        'new_holdout': False, 'human_reviewed': False, 'release_gate_passed': False}
    return {'baseline': baseline, 'metadata': metadata}


def _refresh(prepared):
    if (type(prepared) is not dict or set(prepared) != {'baseline', 'metadata'}
            or type(prepared['baseline']) is not dict or type(prepared['baseline'].get('paths')) is not list
            or len(prepared['baseline']['paths']) != 3):
        raise ValueError('INVALID_EVALUATION_PREFLIGHT')
    latest = prepare_probe(*prepared['baseline']['paths'])
    # Includes in-memory document/gold contents, not only their claimed hashes.
    if latest != prepared:
        raise ValueError('EXPERIMENT_CHANGED')
    return latest


def _new_directory(output):
    path = Path(output).absolute()
    if (path.exists() or path.is_symlink() or not path.parent.is_dir()
            or path.parent.resolve() != path.parent):
        raise ValueError('INVALID_CHECKPOINT')
    return path


def _read_probe(path, case):
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError
        raw = read_bytes(path, MAX_TRACE_BYTES)
        return validate_probe_report(case['document'], case['case_id'], json.loads(raw))
    except (ValueError, TypeError, OSError, UnicodeError, RecursionError):
        raise ValueError('INVALID_CHECKPOINT') from None


async def run_probe(prepared, output, nvidia_key, access_file) -> dict:
    prepared = _refresh(prepared)
    baseline, metadata = prepared['baseline'], prepared['metadata']
    cases = {case['case_id']: case for case in baseline['cases']}
    for ident in CASES:
        case = cases[ident]
        _validate_input(case['document'], ident, case['gold'], nvidia_key)
    validate_free_access(access_file, reserved_calls=64)
    output = _new_directory(output)
    output.mkdir(exist_ok=False)
    _write_new(output / 'experiment.json', metadata)
    began, rows = monotonic(), []
    for index, ident in enumerate(CASES):
        _refresh(prepared)
        remaining = MAX_SECONDS - (monotonic() - began)
        if remaining <= 0:
            raise ValueError('PROBE_BUDGET_EXHAUSTED')
        access = validate_free_access(access_file, reserved_calls=(index + 1) * 64)
        case = cases[ident]
        identity = {**_identity(case, 0, baseline['metadata']), 'tool_sha256': metadata['tool_sha256'],
                    'free_access_sha256': digest_json(access)}
        stem = f'{ident}-run-0'
        trace_path = output / (stem + '.trace.json')
        _write_new(output / (stem + '.started.json'), {'version': 'candidate-provenance-start-v1', **identity})
        started, diagnostics = monotonic(), {}
        # The existing scorer keeps gold in this parent; child stdin receives only
        # the ordinary analysis request and credentials through its existing guard.
        score = await run_scored_process(case['document'], ident, case['gold'], nvidia_key,
            timeout_seconds=min(1800, remaining), call_diagnostics=diagnostics, review_model=MODEL,
            command=[sys.executable, '-m', 'diagnostic_tools.candidate_trace_worker', str(trace_path)])
        elapsed = monotonic() - started
        _refresh(prepared)
        row = {**identity, 'elapsed_seconds': round(elapsed, 6), 'score': score, 'diagnostics': diagnostics}
        _diagnostic_row(case, identity, row, review_model=MODEL)
        probe = _read_probe(trace_path, case)
        if (score['status'] == 'valid' and probe['status'] == 'available'
                and probe['trace']['status'] != 'complete'):
            raise ValueError('INVALID_CHECKPOINT')
        record = {**row, 'probe': probe}
        _write_new(output / (stem + '.json'), record)
        if read_json(output / (stem + '.json')) != record:
            raise ValueError('INVALID_CHECKPOINT')
        rows.append(record)
        if score['error'] in STOP_CODES or any(c['provider_error'] for c in diagnostics['calls']):
            raise ValueError('EVALUATION_PROVIDER_STOPPED')
        if probe['status'] != 'available':
            raise ValueError('PROBE_OBSERVATION_UNAVAILABLE')
    _refresh(prepared)
    summary = {'version': 'candidate-provenance-summary-v1', 'expected': len(CASES), 'completed': len(rows),
        'valid': sum(row['score']['status'] == 'valid' for row in rows),
        'failed': sum(row['score']['status'] == 'failed' for row in rows),
        'invalid': sum(row['score']['status'] == 'invalid' for row in rows),
        'reserved_model_calls_upper_bound': len(rows) * 64,
        'observed_calls': sum(len(row['diagnostics']['calls']) for row in rows),
        'human_reviewed': False, 'release_gate_passed': False}
    _write_new(output / 'summary.json', summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline preflight or one immutable three-document diagnostic.')
    parser.add_argument('--live', action='store_true')
    for name in ('corpus', 'gold', 'freeze'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('env-file', 'output', 'access-confirmation'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args(argv)
    try:
        prepared = prepare_probe(args.corpus, args.gold, args.freeze)
        if not args.live:
            summary = {'mode': 'preflight', 'cases': list(CASES), 'metadata': prepared['metadata'],
                       'release_gate_passed': False}
        else:
            validate_free_access(args.access_confirmation, reserved_calls=64)
            if args.env_file is None or args.output is None:
                raise ValueError('INVALID_EVALUATION_INPUT')
            _new_directory(args.output)
            key = load_nvidia_key(args.env_file)
            summary = asyncio.run(run_probe(prepared, args.output, key, args.access_confirmation))
    except KeyboardInterrupt:
        print(json.dumps({'error': 'EVALUATION_INTERRUPTED'}))
        return 1
    except Exception as error:
        code = str(error) if type(error) is ValueError and str(error) in ERROR_CODES else 'EVALUATION_FAILED'
        print(json.dumps({'error': code}))
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
