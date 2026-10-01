"""Fixed candidate-stage comparison. Free-account attestation checked on every call."""
import hashlib
import json
from pathlib import Path
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ai_service'))
from agentfit_ai.candidate_first_profile import classify_profile_candidates
from agentfit_ai.candidate_semantic_assessment import classify_grounded_candidates
from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.nvidia_evaluation_inputs import load_nvidia_key, validate_free_access
from agentfit_ai.nvidia_streaming import post_nvidia_streaming
from agentfit_ai.solar import AnalysisError

INPUT = ROOT / 'ai_service/tests/fixtures/semantic_confirmation_cases.json'
OUT = Path('E:/AgentFit/output/semantic-confirmation-guard-v2')
ACCESS = Path('E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json')
FILES = [INPUT, Path(__file__), ROOT / 'specs/ai-developer/semantic-confirmation-guard/spec.md'] + [
    ROOT / 'ai_service/agentfit_ai' / (name + '.py') for name in (
        'candidate_semantic_assessment', 'candidate_first_profile', 'candidate_field_semantics',
        'candidate_field_review', 'candidate_split_review', 'operation_candidates',
        'deepseek_evaluation', 'solar', 'nvidia_streaming', 'nvidia_evaluation_inputs')]


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.write('\n')


def identity():
    return {'files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES},
            'model': MODEL, 'max_calls': 12, 'retries': 0, 'per_call_seconds': 600,
            'total_seconds': 7200, 'repetitions': 2, 'human_reviewed': False,
            'endpoint': 'https://integrate.api.nvidia.com/v1/chat/completions'}


def metrics(case, labels, records):
    gold = case['gold']; by_id = {r['id']: r for r in labels}
    positive = [r for r in gold if r['confirmed']]
    correct = lambda row: by_id[row['id']]['status'] == 'confirmed' and by_id[row['id']]['field'] == row['field']
    wrong = [r['id'] for r in gold if by_id[r['id']]['status'] == 'confirmed' and
             (not r['confirmed'] or not correct(r))]
    missing = [r['id'] for r in positive if not correct(r)]
    held = [r for r in records if r['decision'] == 'needs_confirmation']
    fields = {r['field'] for r in labels if r['status'] == 'confirmed' and r['field'] != 'other'}
    for r in held:
        fields.update([r['field']] if r['field'] != 'other' else [
            'project_name', 'project_type', 'domain', 'frontend', 'backend', 'ai', 'database',
            'deployment', 'features', 'external_integrations'])
    return {'false_confirmations': len(wrong), 'false_ids': wrong,
            'positive_count': len(positive), 'positive_misses': len(missing), 'missing_ids': missing,
            'held_candidates': len(held), 'held_ids': [r['id'] for r in held],
            'field_questions_projection_only': len(fields)}


def main():
    if sys.argv[-1] == 'freeze':
        validate_free_access(ACCESS, reserved_calls=12)
        OUT.mkdir(exist_ok=True)
        write(OUT / 'freeze.json', identity())
        print('freeze written; calls=0', flush=True)
        return
    frozen = json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))
    if identity() != frozen:
        raise ValueError('EXPERIMENT_CHANGED')
    validate_free_access(ACCESS, reserved_calls=12)
    cases = json.loads(INPUT.read_text(encoding='utf-8'))['cases']
    key = load_nvidia_key(Path('E:/AgentFit/.env'))
    calls, started, stopped = [], monotonic(), False

    def transport(payload, api_key, timeout):
        nonlocal stopped
        access = validate_free_access(ACCESS, reserved_calls=12)
        if (stopped or len(calls) >= 12 or monotonic() - started >= 7200 or
                payload.get('model') not in access['models'] or payload.get('model') != MODEL):
            raise AnalysisError('PROVIDER_FAILURE')
        if identity() != frozen:
            raise ValueError('EXPERIMENT_CHANGED')
        row = {'index': len(calls) + 1, 'completed': False, 'elapsed_seconds': None}
        calls.append(row)
        begin = monotonic()
        try:
            raw = post_nvidia_streaming(payload, api_key, min(timeout, 7200 - (begin - started)))
            row['completed'] = True
            return raw
        except Exception:
            stopped = True
            raise
        finally:
            row['elapsed_seconds'] = round(monotonic() - begin, 3)
            print(json.dumps({'call': row}), flush=True)

    results = []
    for repetition in range(2):
        for case in cases:
            for mode in ('baseline', 'guarded'):
                name = f"{case['id']}-{mode}-{repetition}"
                write(OUT / (name + '.started.json'), {'case': case['id'], 'mode': mode, 'repetition': repetition})
                item = {'case': case['id'], 'mode': mode, 'repetition': repetition,
                        'status': 'failed', 'error': None, 'labels': None, 'modelDecisions': None, 'metrics': None}
                begin, first_call = monotonic(), len(calls)
                try:
                    if mode == 'baseline':
                        labels = classify_profile_candidates(case['document'], case['frozen'], key,
                            transport=transport, nvidia_model=MODEL, field_semantics='explicit-v1', batch_size=15)
                        records = []
                    else:
                        answer = classify_grounded_candidates(case['document'], case['frozen'], key,
                                                              model=MODEL, transport=transport)
                        labels, records = answer['labels'], answer['modelDecisions']
                    item.update(status='valid', labels=labels, modelDecisions=records,
                                metrics=metrics(case, labels, records))
                except Exception as error:
                    item['error'] = error.code if isinstance(error, AnalysisError) else type(error).__name__
                    stopped = True
                item['elapsed_seconds'] = round(monotonic() - begin, 3)
                item['calls'] = calls[first_call:]
                write(OUT / (name + '.json'), item)
                results.append({k: v for k, v in item.items() if k not in ('labels', 'modelDecisions', 'calls')})
                print(json.dumps(results[-1]), flush=True)
                if stopped:
                    break
            if stopped: break
        if stopped: break
    write(OUT / 'summary.json', {'results': results, 'calls': calls, 'planned_requests': 8,
          'attempted_requests': len(results), 'stopped': stopped, 'human_reviewed': False,
          'release_gate_passed': False})


if __name__ == '__main__':
    main()
