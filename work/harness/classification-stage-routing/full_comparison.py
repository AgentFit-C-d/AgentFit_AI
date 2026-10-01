"""Preregistered classification-only diagnostic; no service defaults or raw output logs."""
import hashlib
import json
import math
from pathlib import Path
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ai_service'))
from agentfit_ai.analysis_call_metadata import build_metadata
from agentfit_ai.candidate_first_profile import classify_profile_candidates, validate_candidate_labels
from agentfit_ai.diagnostics import safe_code
from agentfit_ai.independent_evaluation_inputs import digest_json, read_bytes, read_json
from agentfit_ai.nvidia_evaluation_inputs import (build_freeze, prepare_evaluation,
                                                load_nvidia_key, validate_free_access)
from agentfit_ai.nvidia_streaming import post_nvidia_streaming
from agentfit_ai.solar import AnalysisError
from diagnostic_tools.candidate_trace import validate_trace

SPEC = ROOT / 'specs/ai-developer/classification-stage-routing'
CORPUS = ROOT / 'specs/ai-developer/04-analysis-provider/independent-profile-evaluation/corpus.json'
BASE = Path('E:/AgentFit/output/independent-profile-v1')
GOLD = BASE / 'gold-v1.json'
ACCESS = BASE / 'nvidia-free-access-20261001-user-confirmation.json'
SOURCE_FREEZE = SPEC / 'source-validation-freeze.json'
FREEZE = SPEC / 'comparison-freeze.json'
OUT = BASE / 'classification-full-batch15-v1'
SYNTHETIC = ROOT / 'specs/ai-developer/runtime-purpose-review/mixed-synthetic.json'
MODELS = ('deepseek-ai/deepseek-v4.1-flash', 'z-ai/glm-5.3')
IDS = ('PUBLIC-01', 'PUBLIC-07', 'SYNTHETIC-01')
ORDER = [(case_id, model) for case_id in IDS for model in MODELS]
MAX_CALLS, TOTAL_SECONDS = 34, 20760


def sha(path, *, lf=False):
    raw = read_bytes(path)
    return hashlib.sha256(raw.replace(b'\r\n', b'\n') if lf else raw).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
        stream.write('\n')


def load_cases(source_freeze=SOURCE_FREEZE):
    prepared = prepare_evaluation(CORPUS, GOLD, source_freeze)
    cases = {}
    for item in prepared['cases']:
        case_id = item['case_id']
        if case_id not in IDS[:2]:
            continue
        path = BASE / 'capability-occurrences-full-v1' / (case_id + '-run-0.trace.json')
        envelope = read_json(path)
        if (envelope['status'] != 'available' or envelope['documentId'] != case_id or
                envelope['sourceSha256'] != item['source_sha256']):
            raise ValueError('INVALID_EVALUATION_PREFLIGHT')
        trace = validate_trace(item['document'], case_id, envelope['trace'])
        grounded = trace['stages']['grounded']
        frozen = {'candidates': grounded['candidates'], 'rejected': []}
        labels = validate_candidate_labels(frozen, trace['stages']['classified']['labels'])
        cases[case_id] = {'document': item['document'], 'frozen': frozen,
            'previous': labels, 'rejected_count': grounded['rejectedCount'],
            'source_sha256': item['source_sha256'], 'trace_sha256': sha(path)}
    source = read_json(SYNTHETIC)
    document, rows, previous = source['document'], [], []
    for i, unit in enumerate(source['units']):
        position = -1
        for _ in range(unit['occurrence'] + 1):
            position = document.find(unit['quote'], position + 1)
            if position < 0:
                raise ValueError('INVALID_EVALUATION_PREFLIGHT')
        candidate_id = f'C{i:03}'
        rows.append({'id': candidate_id, 'start': position, 'end': position + len(unit['quote'])})
        previous.append({'id': candidate_id, 'field': unit.get('field', 'features'), 'status': 'confirmed'})
    cases['SYNTHETIC-01'] = {'document': document,
        'frozen': {'candidates': rows, 'rejected': []}, 'previous': previous,
        'rejected_count': 0, 'source_sha256': hashlib.sha256(document.encode()).hexdigest(),
        'trace_sha256': None}
    if [len(cases[c]['frozen']['candidates']) for c in IDS] != [173, 36, 16]:
        raise ValueError('INVALID_EVALUATION_PREFLIGHT')
    return cases


def identity(cases):
    return {'version': 'classification-full-batch15-v1', 'order': ORDER,
        'script_sha256': sha(__file__, lf=True),
        'plan_sha256': sha(SPEC / 'comparison-plan.md', lf=True),
        'source_validation_sha256': digest_json(read_json(SOURCE_FREEZE)),
        'diagnostic_files': {p.name: sha(p, lf=True)
                            for p in sorted((ROOT / 'ai_service/diagnostic_tools').glob('*.py'))},
        'access_sha256': sha(ACCESS), 'synthetic_sha256': sha(SYNTHETIC),
        'cases': {c: {k: v for k, v in case.items() if k in
                     ('source_sha256', 'trace_sha256', 'rejected_count')} |
                    {'frozen_sha256': digest_json(case['frozen']),
                     'previous_sha256': digest_json(case['previous']),
                     'candidates': len(case['frozen']['candidates'])}
                  for c, case in cases.items()},
        'models': list(MODELS), 'batch_size': 15, 'field_semantics': 'explicit-v1',
        'max_tokens': 8192, 'provider_seconds': 600, 'max_calls': MAX_CALLS,
        'total_seconds': TOTAL_SECONDS, 'retry_limit': 0,
        'human_reviewed': False, 'release_gate_passed': False}


def preflight():
    validate_free_access(ACCESS, reserved_calls=MAX_CALLS)
    cases = load_cases()
    if digest_json(identity(cases)) != digest_json(read_json(FREEZE)):
        raise ValueError('EXPERIMENT_CHANGED')
    return cases


def classify(case, model, key, *, guard, deadline, transport=post_nvidia_streaming):
    calls, labels, error = [], [], None
    limit = math.ceil(len(case['frozen']['candidates']) / 15)
    def send(payload, supplied_key, timeout):
        guard()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise AnalysisError('PROVIDER_TIMEOUT')
        if len(calls) >= limit or payload['model'] != model or supplied_key != key:
            raise ValueError('INVALID_EVALUATION_PREFLIGHT')
        row = {'stage': 'CLASSIFICATION_FAILED', 'provider': 'nvidia',
            'requested_model': model, 'call_index': len(calls) + 1, 'elapsed_ms': 0,
            'response_bytes': None, 'transport_completed': False, 'attempt': 1,
            'retry_of_call_index': None, 'provider_error': None}
        started = monotonic()
        calls.append(row)
        try:
            raw = transport(payload, key, min(timeout, remaining))
            if type(raw) is not bytes:
                raise AnalysisError('INVALID_RESPONSE')
            row['transport_completed'], row['response_bytes'] = True, len(raw)
            return raw
        except AnalysisError as caught:
            row['provider_error'] = safe_code(caught.code)
            raise
        except Exception:
            row['provider_error'] = 'PROVIDER_FAILURE'
            raise AnalysisError('PROVIDER_FAILURE') from None
        finally:
            row['elapsed_ms'] = round((monotonic() - started) * 1000)
    started = monotonic()
    try:
        guard()
        labels = classify_profile_candidates(case['document'], case['frozen'], key,
            nvidia_model=model, batch_size=15, field_semantics='explicit-v1', transport=send)
        guard()
        if len(calls) != limit or monotonic() > deadline:
            raise ValueError('INVALID_EVALUATION_PREFLIGHT')
    except AnalysisError as caught:
        error = safe_code(caught.code)
    except ValueError as caught:
        allowed = ('FREE_ACCESS_UNCONFIRMED', 'FREE_ACCESS_BUDGET_EXHAUSTED',
                   'EXPERIMENT_CHANGED', 'INVALID_EVALUATION_PREFLIGHT')
        error = caught.args[0] if len(caught.args) == 1 and caught.args[0] in allowed else 'CLASSIFICATION_FAILED'
    except Exception:
        error = 'CLASSIFICATION_FAILED'
    if error is not None:
        labels = []
    return {'status': 'valid' if error is None else 'failed', 'error': error,
        'labels': labels, 'elapsed_seconds': round(monotonic() - started, 6),
        'metadata': build_metadata(calls, 'CLASSIFICATION_FAILED' if error else None)}


def prior_hashes():
    return {p.relative_to(BASE).as_posix(): sha(p) for p in sorted(BASE.rglob('*.json'))
            if OUT not in p.parents}


def live():
    cases = preflight()
    if OUT.exists():
        raise ValueError('OUTPUT_EXISTS')
    key = load_nvidia_key(Path('E:/AgentFit/.env'))
    prior = prior_hashes()
    OUT.mkdir()
    save(OUT / 'registration.json', {'freeze_sha256': digest_json(read_json(FREEZE)),
                                    'prior_json': prior})
    deadline, results = monotonic() + TOTAL_SECONDS, []
    for case_id, model in ORDER:
        # An observation timeout does not restart this single serial run.
        case = cases[case_id]
        alias = 'deepseek' if model == MODELS[0] else 'glm'
        stem = f'{case_id}-{alias}'
        save(OUT / (stem + '.started.json'), {'case_id': case_id, 'model': model,
            'source_sha256': case['source_sha256'], 'max_calls': math.ceil(len(case['frozen']['candidates']) / 15)})
        request_deadline = min(deadline, monotonic() + math.ceil(len(case['frozen']['candidates']) / 15) * 600 + 60)
        result = classify(case, model, key, guard=preflight, deadline=request_deadline)
        row = {'case_id': case_id, 'model': model, 'source_sha256': case['source_sha256'], **result}
        save(OUT / (stem + '.json'), row)
        results.append(row)
        print(json.dumps({'case_id': case_id, 'model': model, 'status': result['status'],
                          'calls': len(result['metadata']['calls']),
                          'seconds': result['elapsed_seconds'], 'error': result['error']}), flush=True)
        if result['status'] != 'valid':
            break
    unchanged = all((BASE / name).is_file() and sha(BASE / name) == digest for name, digest in prior.items())
    summary = {'completed_requests': len(results), 'all_valid': len(results) == 6 and
        all(r['status'] == 'valid' for r in results),
        'model_calls': sum(len(r['metadata']['calls']) for r in results),
        'prior_json_unchanged': unchanged, 'prior_json_count': len(prior),
        'human_reviewed': False, 'release_gate_passed': False}
    save(OUT / 'summary.json', summary)
    if not unchanged or not summary['all_valid']:
        raise ValueError('COMPARISON_STOPPED')


def main():
    if sys.argv[1:] == ['--register']:
        if OUT.exists() or SOURCE_FREEZE.exists() or FREEZE.exists():
            raise ValueError('REGISTRATION_EXISTS')
        validate_free_access(ACCESS, reserved_calls=MAX_CALLS)
        save(SOURCE_FREEZE, build_freeze(CORPUS, GOLD))
        save(FREEZE, identity(load_cases()))
        print('registered', digest_json(read_json(FREEZE)))
    elif sys.argv[1:] == ['--preflight']:
        cases = preflight()
        print(json.dumps({'cases': {c: len(v['frozen']['candidates']) for c, v in cases.items()},
                          'max_calls': MAX_CALLS, 'output_exists': OUT.exists()}))
    elif sys.argv[1:] == ['--live']:
        live()
    else:
        raise ValueError('INVALID_COMMAND')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('COMPARISON_STOPPED: preflight, local contract, or recorded provider failure', file=sys.stderr)
        raise SystemExit(1) from None
