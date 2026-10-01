"""Classification-instruction-only experiment; never imported by the service."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location('instruction_unit_baseline',
    ROOT / 'work/harness/b-evidence-selection-comparison/experiment.py')
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)
MODEL, AnalysisError, write_json = baseline.MODEL, baseline.AnalysisError, baseline.write_json


def build_instruction_pair(document: str, frozen: dict, clarification: str) -> dict:
    if not isinstance(clarification, str) or not clarification.strip() or '\r' in clarification:
        raise ValueError('INVALID_CLARIFICATION')
    original = baseline.build_pair(document, frozen)
    unit = original['payloads']['U']
    clarified = deepcopy(unit)
    for payload in clarified:
        payload['messages'][0]['content'] += '\n' + clarification
    return {'registry': original['registry'], 'payloads': {'U': unit, 'U+C': clarified}}


def score_instruction_rows(records: list, diagnostics: list, gold: list) -> dict:
    expected = {g['candidateId']: g for g in gold}
    by_id, evidence = {r['id']: r for r in records}, {d['id']: d for d in diagnostics}
    if (len(expected) != len(gold) or len(by_id) != len(records) or len(evidence) != len(diagnostics)
            or not set(by_id) <= set(expected) or set(by_id) != set(evidence)):
        raise ValueError('INVALID_SCORE_INPUT')
    details = []
    for g in gold:
        r, d = by_id.get(g['candidateId']), evidence.get(g['candidateId'])
        positive = g['scored'] and g['expectedStatus'] == 'confirmed'
        correct = r is not None and (r['raw_field'], r['raw_status']) == (g['expectedField'], g['expectedStatus'])
        raw_false = bool(g['scored'] and r and r['raw_field'] in baseline.FIELDS
                         and r['raw_status'] == 'confirmed' and not correct)
        held = bool(r and r['verdict'] == 'needs_confirmation')
        supported = bool(correct and r['verdict'] == 'supported')
        details.append({'caseId': g['caseId'], 'candidateId': g['candidateId'], 'scored': g['scored'],
            'expected': {k: g[k] for k in ('expectedField', 'expectedStatus', 'expectedVerdict')},
            'positive': positive, 'core_positive': positive and g['category'] in ('feature', 'integration'),
            'actual': deepcopy(r), 'citation': deepcopy(d), 'unassessable': r is None,
            'raw_false_confirmed': raw_false,
            'false_supported': bool(raw_false and r['verdict'] == 'supported'),
            'raw_normal_missing': bool(positive and not correct),
            'normal_missing': bool(positive and not supported),
            'positive_supported': bool(positive and supported),
            'held': held, 'held_normal': bool(positive and held),
            'raw_mismatch': bool(g['scored'] and r and not correct),
            'correct_excluded': bool(g['scored'] and g['expectedVerdict'] == 'excluded'
                                     and correct and r['verdict'] == 'excluded')})
    metrics = {key: sum(int(d[key]) for d in details) for key in
               ('raw_false_confirmed', 'false_supported', 'raw_normal_missing', 'normal_missing',
                'positive_supported', 'held_normal', 'correct_excluded', 'raw_mismatch', 'unassessable')}
    return {**metrics, 'total': len(gold), 'scored': sum(g['scored'] for g in gold),
        'positive_gold': sum(d['positive'] for d in details), 'retained': len(records),
        'complete': len(records) == len(gold),
        'core_positive_gold': sum(d['core_positive'] for d in details),
        'core_positive_supported': sum(d['core_positive'] and d['positive_supported'] for d in details),
        'held_total': sum(d['held'] for d in details),
        'held_scored': sum(d['held'] and d['scored'] for d in details),
        'held_ambiguous': sum(d['held'] and not d['scored'] for d in details),
        'citation_defects': sum(d['citationDefect'] for d in diagnostics),
        'citation_unassessable': len(gold)-len(diagnostics),
        'citation_kinds': dict(Counter(d['kind'] for d in diagnostics)), 'details': details}


def safe_error(exc):
    if isinstance(exc, AnalysisError):
        return baseline.error_code(exc)
    allowed = {'CALLS_STOPPED', 'FREE_ACCESS_UNCONFIRMED', 'FREE_ACCESS_BUDGET_EXHAUSTED',
               'FROZEN_INPUT_OR_CODE_CHANGED', 'PAYLOAD_ORDER_CHANGED', 'DEADLINE_EXPIRED',
               'INVALID_REPLY_ROOT', 'INVALID_UNIT_DECISIONS', 'INVALID_SCORE_INPUT'}
    return str(exc) if type(exc) is ValueError and str(exc) in allowed else type(exc).__name__


class EightCallGate:
    """Exact frozen request sequence, eight attempts total, terminal failure, no retry."""
    def __init__(self, output, jobs, *, check_free, check_identity, transport):
        if len(jobs) != 8:
            raise ValueError('INVALID_JOB_COUNT')
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        if list(self.output.iterdir()):
            raise ValueError('CALL_DIRECTORY_NOT_EMPTY')
        self.jobs = deepcopy(jobs)
        self.check_free, self.check_identity, self.transport = check_free, check_identity, transport
        self.started, self.stopped, self.stop_reason = 0, False, None
        self.completed = []
        self.start = time.monotonic()

    def __call__(self, payload, key, timeout):
        if self.stopped or self.started >= 8:
            raise ValueError('CALLS_STOPPED')
        try:
            self.check_free()
            self.check_identity()
            job = self.jobs[self.started]
            if payload.get('model') != MODEL or json.dumps(payload) != json.dumps(job['payload']):
                raise ValueError('PAYLOAD_ORDER_CHANGED')
            limit = min(float(timeout), 600, 5400-(time.monotonic()-self.start))
            if limit <= 0:
                raise ValueError('DEADLINE_EXPIRED')
            sequence = self.started+1
            prefix = self.output / f'{sequence:02d}'
            label = {k: job[k] for k in ('docId', 'arm', 'batch')}
            write_json(str(prefix)+'-request.json', payload)
            write_json(str(prefix)+'-started.json', dict(label, sequence=sequence,
                utc=datetime.now(timezone.utc).isoformat(), timeout_seconds=limit))
            self.started += 1
            start = time.monotonic()
            metadata = dict(label, sequence=sequence, returned=False, error='INTERRUPTED')
            try:
                raw = self.transport(payload, key, limit)
                with Path(str(prefix)+'-response.json').open('xb') as handle:
                    handle.write(raw)
                metadata.update(returned=True, error=None)
                return raw
            except Exception as exc:
                metadata['error'] = safe_error(exc)
                raise
            finally:
                metadata['seconds'] = time.monotonic()-start
                write_json(str(prefix)+'-finished.json', metadata)
                self.completed.append(metadata)
        except Exception as exc:
            self.stopped, self.stop_reason = True, safe_error(exc)
            raise
