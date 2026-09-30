"""Frozen synthetic regression for relation judgment, not end-to-end accuracy."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from .candidate_feature_curation import _feature_candidates, _validate_partition
from .candidate_feature_relations import review_feature_relations
from .deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS, load_key
from .diagnostics import safe_code
from .false_complete_evaluation import write_safe_json
from .solar import AnalysisError


_DEFINITE = ('covered', 'not_covered')
_COVERAGE = (*_DEFINITE, 'uncertain')
_ORDERS = ('original', 'reversed')
DEFAULT_CORPUS = (Path(__file__).resolve().parents[2] /
    'specs/ai-developer/04-analysis-provider/feature-relation-regression/cases.json')


def _anchor(document, selector, *, distractor=False):
    keys = {'quote', 'occurrence', 'status'} if distractor else {'quote', 'occurrence'}
    if type(selector) is not dict or set(selector) != keys:
        raise ValueError('invalid source selector')
    quote, occurrence = selector['quote'], selector['occurrence']
    if (type(quote) is not str or not quote.strip() or type(occurrence) is not int or
            occurrence < 0 or (distractor and (
                type(selector['status']) is not str or
                selector['status'] not in ('negated', 'tentative')))):
        raise ValueError('invalid source selector')
    # Advancing by one preserves overlapping occurrences. Never select another match.
    start, search_at, found = -1, 0, 0
    while (start := document.find(quote, search_at)) != -1:
        if found == occurrence:
            return start, start + len(quote)
        search_at, found = start + 1, found + 1
    raise ValueError('source occurrence missing')


def prepare_case(case):
    if type(case) is not dict or set(case) != {
            'id', 'document', 'representative', 'member', 'distractors', 'expected'}:
        raise ValueError('invalid relation case')
    document = case['document']
    if (type(case['id']) is not str or not re.fullmatch(r'FR[0-9]{2}', case['id']) or
            type(document) is not str or not document.strip() or len(document) > 100_000 or
            type(case['expected']) is not str or case['expected'] not in _DEFINITE or
            type(case['distractors']) is not list or len(case['distractors']) > 238):
        raise ValueError('invalid relation case')
    candidates, labels, spans = [], [], set()
    for index, selector in enumerate([case['representative'], case['member'], *case['distractors']]):
        start, end = _anchor(document, selector, distractor=index >= 2)
        if (start, end) in spans:
            raise ValueError('duplicate source occurrence')
        spans.add((start, end))
        cid = f'C{index:03d}'
        candidates.append({'id': cid, 'start': start, 'end': end})
        labels.append({'id': cid, 'field': 'features',
                       'status': 'confirmed' if index < 2 else selector['status']})
    frozen = {'candidates': candidates, 'rejected': []}
    partition = {'groups': [{'representativeId': 'C000', 'memberIds': ['C000', 'C001']}],
                 'unrepresentedIds': []}
    _validate_partition(_feature_candidates(document, frozen, labels), partition)
    return {'id': case['id'], 'expected': case['expected'], 'document': document,
            'frozen': frozen, 'labels': labels, 'partition': partition}


def _prepare_cases(cases):
    if type(cases) is not list or not 1 <= len(cases) <= 24:
        raise ValueError('invalid relation corpus size')
    prepared = [prepare_case(case) for case in cases]
    if len({case['id'] for case in prepared}) != len(prepared):
        raise ValueError('duplicate case id')
    return prepared


def load_cases(path, expected_sha256):
    if type(expected_sha256) is not str or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('invalid corpus hash')
    raw = Path(path).read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('corpus hash mismatch')
    try:
        corpus = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError):
        raise ValueError('invalid relation corpus JSON') from None
    if type(corpus) is not dict or set(corpus) != {'cases'}:
        raise ValueError('invalid relation corpus')
    _prepare_cases(corpus['cases'])
    return corpus['cases']


def _summary(rows, case_ids, repeats):
    planned = len(case_ids) * 2 * repeats
    by_key = {(r['case_id'], r['order'], r['repeat']): r['actual'] for r in rows}
    def consistent(values):
        return all(v in _DEFINITE for v in values) and len(set(values)) == 1
    order_matches = sum(consistent([by_key.get((cid, order, repeat)) for order in _ORDERS])
                        for cid in case_ids for repeat in range(1, repeats + 1))
    repeat_matches = sum(consistent([by_key.get((cid, order, repeat))
                         for repeat in range(1, repeats + 1)])
                         for cid in case_ids for order in _ORDERS) if repeats > 1 else 0
    matched = sum(r['actual'] == r['expected'] for r in rows)
    return {'planned': planned, 'completed': len(rows), 'matched': matched,
            'false_covered': sum(r['actual'] == 'covered' and r['expected'] == 'not_covered' for r in rows),
            'false_uncovered': sum(r['actual'] == 'not_covered' and r['expected'] == 'covered' for r in rows),
            'uncertain': sum(r['actual'] == 'uncertain' for r in rows),
            'failed': sum(r['actual'] == 'failed' for r in rows),
            'order_consistency': {'matched': order_matches, 'planned': len(case_ids) * repeats},
            'repeat_consistency': {'matched': repeat_matches, 'planned': len(case_ids) * 2 if repeats > 1 else 0},
            'gate_passed': len(rows) == planned and matched == planned,
            'rows': copy.deepcopy(rows)}


def _safe_trace(trace):
    safe = {}
    if trace.get('model') in NVIDIA_REVIEW_MODELS:
        safe['model'] = trace['model']
    if trace.get('finish_reason') in ('stop', 'length', 'content_filter', 'tool_calls'):
        safe['finish_reason'] = trace['finish_reason']
    for name in ('candidate_count', 'relation_count', 'server_covered_count',
                 'unrepresented_count', 'covered_count', 'not_covered_count',
                 'uncertain_count', 'prompt_tokens', 'completion_tokens',
                 'provider_elapsed_ms', 'request_bytes', 'response_bytes'):
        value = trace.get(name)
        if type(value) is int and value >= 0:
            safe[name] = value
    return safe


def evaluate_cases(cases, key, *, model=MODEL, repeats=2, transport=None, checkpoint=None):
    if (type(key) is not str or not key.strip() or type(model) is not str or
            model not in NVIDIA_REVIEW_MODELS or type(repeats) is not int or
            not 1 <= repeats <= 3 or (transport is not None and not callable(transport)) or
            (checkpoint is not None and not callable(checkpoint))):
        raise ValueError('invalid relation evaluation options')
    prepared = _prepare_cases(cases)  # Validate the entire run before any paid request.
    rows, ids = [], [case['id'] for case in prepared]
    for case in prepared:
        for order in _ORDERS:
            frozen = copy.deepcopy(case['frozen'])
            if order == 'reversed':
                frozen['candidates'].reverse()
            for repeat in range(1, repeats + 1):
                traces, start = [], time.monotonic()
                row = {'case_id': case['id'], 'order': order, 'repeat': repeat,
                       'expected': case['expected'], 'actual': 'failed'}
                try:
                    result = review_feature_relations(case['document'], frozen, case['labels'],
                        case['partition'], key, model=model, transport=transport, call_trace=traces)
                    if len(traces) != 1 or traces[0].get('validated') is not True:
                        raise ValueError('invalid relation trace')
                    counts = [traces[0].get(name + '_count') for name in _COVERAGE]
                    if any(type(n) is not int or n not in (0, 1) for n in counts) or sum(counts) != 1:
                        raise ValueError('invalid relation counts')
                    actual = _COVERAGE[counts.index(1)]
                    if result['uncoveredIds'] != ([] if actual == 'covered' else ['C001']):
                        raise ValueError('inconsistent relation result')
                    row['actual'] = actual
                except AnalysisError as error:
                    row['error'] = safe_code(error.code)
                except ValueError:
                    row['error'] = 'INVALID_FEATURE_RELATIONS'
                row['elapsed_ms'] = round((time.monotonic() - start) * 1000)
                row['provider'] = _safe_trace(traces[-1]) if traces else {}
                rows.append(row)
                if checkpoint is not None:
                    checkpoint(_summary(rows, ids, repeats))  # Disk errors stop the run.
    return _summary(rows, ids, repeats)


def code_hashes():
    """Cover all local analyzer dependencies, including the evaluation runner."""
    root = Path(__file__).resolve().parent
    return {path.name: hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for path in sorted(root.glob('*.py'))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight', action='store_true')
    modes.add_argument('--live', action='store_true')
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS)
    parser.add_argument('--corpus-sha256', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--model', choices=NVIDIA_REVIEW_MODELS, default=MODEL)
    parser.add_argument('--repeats', type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args(argv)
    if args.live and args.output is None:
        parser.error('--output required for live evaluation')
    if args.output is not None and (os.path.lexists(args.output) or not args.output.parent.is_dir()):
        parser.error('output must be a new file in an existing directory')
    try:
        cases = load_cases(args.corpus, args.corpus_sha256)
        before = code_hashes()
    except (OSError, ValueError):
        parser.error('invalid corpus, hash or code files')
    metadata = {'corpus_sha256': args.corpus_sha256, 'code_hashes': before,
                'model': args.model, 'repeats': args.repeats,
                'orders': list(_ORDERS), 'scope': 'synthetic_feature_relations'}
    initial = _summary([], [case['id'] for case in cases], args.repeats)
    if args.preflight:
        print(json.dumps({'state': 'preflight', 'planned': initial['planned'],
            'corpus_sha256': args.corpus_sha256, 'model': args.model,
            'repeats': args.repeats, 'code_file_count': len(before)}), flush=True)
        return 0
    try:
        key = load_key(args.env_file)
        if type(key) is not str or not key.strip():
            raise ValueError('empty key')
        # Exclusive creation protects an existing report even after the earlier check.
        with args.output.open('x', encoding='utf-8'):
            pass
    except (OSError, ValueError):
        parser.error('key unavailable or output creation failed')

    def checkpoint(summary):
        write_safe_json(args.output, {**metadata, 'state': 'in_progress', **summary},
                        forbidden_strings=(key,))
        print(json.dumps({'state': 'in_progress', 'completed': summary['completed'],
            'planned': summary['planned'], 'matched': summary['matched'],
            'failed': summary['failed']}), flush=True)

    try:
        checkpoint(initial)
        report = evaluate_cases(cases, key, model=args.model, repeats=args.repeats,
                                checkpoint=checkpoint)
        after = code_hashes()
        unchanged = before == after
        report = {**metadata, **report, 'state': 'finished', 'code_unchanged': unchanged,
                  'code_hashes_after': after, 'gate_passed': report['gate_passed'] and unchanged}
        write_safe_json(args.output, report, forbidden_strings=(key,))
        print(json.dumps({name: report[name] for name in (
            'state', 'planned', 'completed', 'matched', 'false_covered', 'false_uncovered',
            'uncertain', 'failed', 'order_consistency', 'repeat_consistency',
            'code_unchanged', 'gate_passed')}), flush=True)
        return 0 if report['gate_passed'] else 1
    except (OSError, ValueError, KeyboardInterrupt):
        # Never display exception text: it can contain key, source, or provider output.
        print('Evaluation interrupted; the last stored checkpoint may be incomplete.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
