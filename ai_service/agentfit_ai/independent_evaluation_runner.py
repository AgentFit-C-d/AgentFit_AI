"""Bounded execution and immutable checkpoints for independent evaluation."""
import asyncio
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

from .independent_evaluation_protocol import validate_score
from .independent_evaluation_inputs import decode_json, prepare_evaluation, read_json, load_keys
from .independent_evaluation_worker import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES, validate_request
from .independent_profile_evaluation import score_confirmation
from .profile import FIELDS
from .solar import _provider_worker_environment


def _failure(document, document_id, gold, code):
    return score_confirmation(document, document_id, gold,
                              {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': code})


async def run_scored_process(document: str, document_id: str, gold: dict, solar_key: str,
                             nvidia_key: str, *, timeout_seconds=1800, command=None) -> dict:
    packet = {'document': document, 'documentId': document_id, 'gold': gold,
              'solarKey': solar_key, 'nvidiaKey': nvidia_key}
    validate_request(packet)
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 1800):
        raise ValueError('INVALID_EVALUATION_INPUT')
    encoded = json.dumps(packet, ensure_ascii=False).encode('utf-8')
    if len(encoded) > MAX_INPUT_BYTES:
        raise ValueError('INVALID_EVALUATION_INPUT')
    process = None
    argv = command if command is not None else [sys.executable, '-m', 'agentfit_ai.independent_evaluation_worker']
    try:
        async with asyncio.timeout(timeout_seconds):
            process = await asyncio.create_subprocess_exec(
                *argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, cwd=Path(__file__).resolve().parents[1],
                env=_provider_worker_environment())
            process.stdin.write(encoded)
            await process.stdin.drain()
            process.stdin.close()
            try:
                output = await process.stdout.readexactly(MAX_OUTPUT_BYTES + 1)
            except asyncio.IncompleteReadError as error:
                output = error.partial
            if len(output) > MAX_OUTPUT_BYTES:
                raise ValueError
            await process.wait()
            if process.returncode != 0:
                raise ValueError
            return validate_score(document, gold, decode_json(output))
    except TimeoutError:
        return _failure(document, document_id, gold, 'ANALYSIS_DEADLINE')
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, RecursionError):
        return _failure(document, document_id, gold, 'ANALYSIS_FAILURE')
    finally:
        if process is not None and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()


def _refresh(prepared):
    if type(prepared) is not dict or set(prepared) != {'cases', 'metadata', 'paths'}:
        raise ValueError('INVALID_EVALUATION_PREFLIGHT')
    if type(prepared['paths']) is not list or len(prepared['paths']) != 3:
        raise ValueError('INVALID_EVALUATION_PREFLIGHT')
    latest = prepare_evaluation(*prepared['paths'])
    if latest['metadata'] != prepared['metadata']:
        raise ValueError('EXPERIMENT_CHANGED')
    return latest


def _write_new(path, value):
    # A partial file is deliberately retained after interruption. Its presence
    # blocks replay, and strict JSON validation makes it a visible failure.
    with path.open('xb') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8'))
        handle.flush()
        os.fsync(handle.fileno())


def _identity(case, run, metadata):
    return {'case_id': case['case_id'], 'run': run, 'source_sha256': case['source_sha256'],
            'gold_sha256': case['gold_sha256'], 'freeze_sha256': metadata['freeze_sha256'],
            'evaluator_sha256': metadata['evaluator_sha256']}


def _validate_row(case, identity, row):
    try:
        if (type(row) is not dict or set(row) != {*identity, 'elapsed_seconds', 'score'}
                or any(type(row[k]) is not type(v) or row[k] != v for k, v in identity.items())
                or type(row['elapsed_seconds']) not in (int, float)
                or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds'] < 0):
            raise ValueError
        validate_score(case['document'], case['gold'], row['score'])
        return row
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError('INVALID_CHECKPOINT') from None


def _read_existing(output, cases, metadata, *, row_validator=None):
    check_row = _validate_row if row_validator is None else row_validator
    rows, allowed = {}, {'experiment.json'}
    for case in cases:
        for run in range(3):
            stem = f'{case["case_id"]}-run-{run}'
            allowed.update((stem + '.json', stem + '.started.json'))
    if any(p.name not in allowed or p.is_symlink() or not p.is_file() for p in output.iterdir()):
        raise ValueError('INVALID_CHECKPOINT')
    for case in cases:
        for run in range(3):
            stem = f'{case["case_id"]}-run-{run}'
            start, terminal = output/(stem+'.started.json'), output/(stem+'.json')
            identity = _identity(case, run, metadata)
            if start.exists():
                try:
                    actual = read_json(start)
                    expected = {'version': 'independent-evaluation-start-v1', **identity}
                    if (type(actual) is not dict or set(actual) != set(expected)
                            or any(type(actual[k]) is not type(v) or actual[k] != v for k, v in expected.items())):
                        raise ValueError
                except (ValueError, TypeError, KeyError, OSError, RecursionError):
                    raise ValueError('INVALID_CHECKPOINT') from None
                if not terminal.exists():
                    raise ValueError('INCOMPLETE_RUN')
            elif terminal.exists():
                raise ValueError('INVALID_CHECKPOINT')
            if terminal.exists():
                try:
                    rows[(case['case_id'], run)] = check_row(case, identity, read_json(terminal))
                except (ValueError, OSError, RecursionError):
                    raise ValueError('INVALID_CHECKPOINT') from None
    return rows


def _summary(rows):
    values = list(rows.values())
    metrics = ('gold', 'produced', 'matched', 'missing', 'known_wrong', 'duplicates', 'unassessed')
    return {'version': 'independent-evaluation-summary-v1', 'expected': 30, 'completed': len(values),
            'failed': sum(r['score']['status'] == 'failed' for r in values),
            'invalid': sum(r['score']['status'] == 'invalid' for r in values),
            'valid': sum(r['score']['status'] == 'valid' for r in values),
            'questions': sum(r['score']['questions'] for r in values),
            'elapsed_seconds': [r['elapsed_seconds'] for r in values],
            'fields': {f: {k: sum(r['score']['fields'][f][k] for r in values) for k in metrics} for f in FIELDS},
            'human_reviewed': False, 'release_gate_passed': False}


async def evaluate(prepared: dict, output: Path, solar_key: str, nvidia_key: str) -> dict:
    prepared = _refresh(prepared)
    cases, metadata = prepared['cases'], prepared['metadata']
    for case in cases:
        validate_request({'document': case['document'], 'documentId': case['case_id'], 'gold': case['gold'],
                          'solarKey': solar_key, 'nvidiaKey': nvidia_key})
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
        if read_json(manifest) != metadata:
            raise ValueError('INVALID_CHECKPOINT')
    rows = _read_existing(output, cases, metadata)
    for case in cases:
        for run in range(3):
            if (case['case_id'], run) in rows:
                continue
            _refresh(prepared)
            identity = _identity(case, run, metadata)
            stem = f'{case["case_id"]}-run-{run}'
            _write_new(output/(stem+'.started.json'), {'version': 'independent-evaluation-start-v1', **identity})
            started = time.monotonic()
            try:
                score = await run_scored_process(case['document'], case['case_id'], case['gold'], solar_key, nvidia_key)
                score = validate_score(case['document'], case['gold'], score)
            except Exception:
                score = _failure(case['document'], case['case_id'], case['gold'], 'ANALYSIS_FAILURE')
            row = {**identity, 'elapsed_seconds': round(time.monotonic() - started, 6), 'score': score}
            _validate_row(case, identity, row)
            path = output/(stem+'.json')
            _write_new(path, row)
            rows[(case['case_id'], run)] = _validate_row(case, identity, read_json(path))
    _refresh(prepared)
    rows = _read_existing(output, cases, metadata)
    if len(rows) != 30:
        raise ValueError('INCOMPLETE_RUN')
    return _summary(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run fixed public evaluation; only typed scores are saved.')
    parser.add_argument('--live', action='store_true')
    for name in ('env-file', 'corpus', 'gold', 'freeze', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({'error': 'LIVE_REQUIRED'}))
        return 2
    try:
        prepared = prepare_evaluation(args.corpus, args.gold, args.freeze)
        solar_key, nvidia_key = load_keys(args.env_file)
        summary = asyncio.run(evaluate(prepared, args.output, solar_key, nvidia_key))
    except KeyboardInterrupt:
        print(json.dumps({'error': 'EVALUATION_INTERRUPTED'}))
        return 1
    except Exception as error:
        codes = {'INVALID_EVALUATION_PREFLIGHT', 'INVALID_EVALUATION_KEYS', 'INVALID_EVALUATION_INPUT',
                 'INVALID_CHECKPOINT', 'INCOMPLETE_RUN', 'EXPERIMENT_CHANGED'}
        code = str(error) if type(error) is ValueError and str(error) in codes else 'EVALUATION_FAILED'
        print(json.dumps({'error': code}))
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
