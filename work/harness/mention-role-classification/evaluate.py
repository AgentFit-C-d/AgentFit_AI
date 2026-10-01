"""Same-input comparison; local injected assertions and live models are distinct."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ai_service'))
from agentfit_ai import candidate_first_profile as first
from agentfit_ai import candidate_semantic_assessment as semantic
from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.nvidia_evaluation_inputs import validate_free_access, load_nvidia_key
from agentfit_ai.nvidia_streaming import post_nvidia_streaming
from agentfit_ai.solar import AnalysisError

OUT = Path('E:/AgentFit/output/mention-role-classification-v1')
FIXTURE = ROOT / 'ai_service/tests/fixtures/mention_role_cases.json'
ACCESS = Path('E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json')
CASES = json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']


def baseline(name):
    spec = importlib.util.spec_from_file_location('agentfit_ai._role_baseline_' + name,
        OUT / ('baseline_' + name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


def metrics(case, labels, records=()):
    labels = {r['id']: r for r in labels}
    held = {r['id'] for r in records if r['decision'] == 'needs_confirmation'} if records else {
        r['id'] for r in labels.values() if r['status'] == 'tentative'}
    false, missing, lost = [], [], []
    for g in case['gold']:
        actual = labels[g['id']]
        confirmed = actual['status'] == 'confirmed'
        if confirmed and ((g['constraint'] == 'positive' and actual['field'] != g['field']) or
                (g['constraint'] == 'not_external' and actual['field'] != 'features') or
                g['constraint'] in ('hold', 'not_confirmed')):
            false.append(g['id'])
        if g['constraint'] == 'positive' and not (confirmed and actual['field'] == g['field']):
            missing.append(g['id'])
        if g['constraint'] == 'hold' and g['id'] not in held:
            lost.append(g['id'])
    return {'candidates': len(case['gold']), 'normal_information': sum(g['constraint'] == 'positive' for g in case['gold']),
            'false_confirmations': len(false), 'normal_misses': len(missing), 'needs_confirmation': len(held),
            'unpreserved_ambiguity': len(lost), 'false_ids': false, 'missing_ids': missing, 'held_ids': sorted(held)}


def fixed_rows(case):
    rows = []
    for g, c in zip(case['gold'], case['frozen']['candidates']):
        # Controlled fault injection, NOT a captured or predicted model response.
        # Positive controls are correct. Descriptions/unknowns carry a wrong confirmed field.
        field = g['field'] if g['constraint'] == 'positive' else 'external_integrations'
        rows.append({'id': g['id'], 'mentionKind': g['kind'], 'field': field,
            'modelStatus': 'confirmed', 'scope': 'target', 'time': 'current', 'polarity': 'positive',
            'commitment': 'adopted', 'role': 'product_fact', 'conflictsChecked': True,
            'support': [{'quote': case['document'][c['start']:c['end']], 'occurrence':
                sum(case['document'].startswith(case['document'][c['start']:c['end']], i) for i in range(c['start']))}],
            'counterEvidence': []})
    return rows


def identity():
    files = [FIXTURE, Path(__file__), *OUT.glob('baseline_*.py')]
    files += [ROOT / 'ai_service/agentfit_ai' / (n + '.py') for n in
        ('candidate_first_profile', 'candidate_semantic_assessment', 'candidate_mention_roles',
         'candidate_field_semantics', 'candidate_field_review', 'candidate_split_review',
         'deepseek_evaluation', 'nvidia_streaming', 'nvidia_evaluation_inputs', 'solar')]
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main():
    mode = sys.argv[1]
    if mode == 'fixed':
        old = baseline('candidate_semantic_assessment'); results = []
        for case in CASES:
            rows = fixed_rows(case)
            before = old.validate_assessments(case['document'], case['frozen'],
                [{k: v for k, v in r.items() if k != 'mentionKind'} for r in rows])
            after = semantic.validate_assessments(case['document'], case['frozen'], rows, require_mention_kind=True)
            results.append({'case': case['id'], 'before': metrics(case, old.semantic_labels(before), before),
                            'after': metrics(case, semantic.semantic_labels(after), after), 'injected_response': rows})
        write(OUT / 'fixed.json', {'kind': 'controlled role assertions, not model accuracy', 'rows': results})
        print(json.dumps([{k: v for k, v in r.items() if k != 'injected_response'} for r in results]))
        return
    if mode == 'freeze':
        validate_free_access(ACCESS, reserved_calls=24)
        write(OUT / 'freeze.json', {'files': identity(), 'model': MODEL, 'max_calls': 24,
            'request_seconds': 180, 'total_seconds': 1800, 'retries': 0, 'repetitions': 1})
        print('frozen; model calls=0'); return
    if mode != 'live': raise ValueError('invalid mode')
    freeze = json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))
    if identity() != freeze['files']: raise ValueError('EXPERIMENT_CHANGED')
    validate_free_access(ACCESS, reserved_calls=24)
    key = load_nvidia_key(Path('E:/AgentFit/.env'))
    old = baseline('candidate_first_profile')
    calls, results, stopped, started = [], [], False, monotonic()

    def transport(payload, api_key, timeout):
        nonlocal stopped
        access = validate_free_access(ACCESS, reserved_calls=24)
        if (stopped or len(calls) >= 24 or monotonic() - started >= 1800 or
                payload.get('model') != MODEL or MODEL not in access['models'] or identity() != freeze['files']):
            raise ValueError('EVALUATION_STOPPED')
        row = {'index': len(calls) + 1, 'completed': False, 'elapsed_seconds': None}
        calls.append(row); begin = monotonic()
        try:
            raw = post_nvidia_streaming(payload, api_key, min(timeout, 180, 1800 - (begin - started)))
            row['completed'] = True; return raw
        except Exception:
            stopped = True; raise
        finally:
            row['elapsed_seconds'] = round(monotonic() - begin, 3)
            print(json.dumps({'call': row}), flush=True)

    for case in CASES:
        for version in ('before', 'after_prompt', 'after_structured'):
            name = case['id'] + '-' + version
            write(OUT / (name + '.started.json'), {'case': case['id'], 'version': version})
            result = {'case': case['id'], 'version': version, 'status': 'failed', 'error': None,
                      'labels': None, 'modelDecisions': None, 'metrics': None}
            try:
                if version == 'after_structured':
                    answer = semantic.classify_grounded_candidates(case['document'], case['frozen'], key,
                        model=MODEL, transport=transport)
                    labels, records = answer['labels'], answer['modelDecisions']
                else:
                    module = old if version == 'before' else first
                    labels = module.classify_profile_candidates(case['document'], case['frozen'], key,
                        transport=transport, nvidia_model=MODEL, field_semantics='explicit-v1', batch_size=15)
                    records = []
                result.update(status='valid', labels=labels, modelDecisions=records, metrics=metrics(case, labels, records))
            except Exception as e:
                result['error'] = e.code if isinstance(e, AnalysisError) else type(e).__name__
                stopped = True
            write(OUT / (name + '.json'), result); results.append(result)
            print(json.dumps({k: v for k, v in result.items() if k not in ('labels', 'modelDecisions')}), flush=True)
            if stopped: break
        if stopped: break
    write(OUT / 'live-summary.json', {'rows': results, 'calls': calls, 'stopped': stopped,
         'human_reviewed': False, 'scope': 'classification of frozen candidates only, one repetition'})


if __name__ == '__main__': main()
