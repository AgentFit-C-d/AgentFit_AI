"""Freeze once, then execute at most one A/B pair. No service changes or retries."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ai_service'))
from comparison import (CallGate, build_payload, normalize_assessments, projection_labels,
                        score_rows, validate_direct, write_json, error_code)
from agentfit_ai.candidate_first_profile import project_candidate_profile
from agentfit_ai.candidate_semantic_assessment import validate_assessments
from agentfit_ai.deepseek_evaluation import MODEL, ENDPOINT, NvidiaAnalyzer
from agentfit_ai.nvidia_evaluation_inputs import validate_free_access, load_nvidia_key
from agentfit_ai.nvidia_streaming import post_nvidia_streaming, ENDPOINT as STREAM_ENDPOINT
from agentfit_ai.operation_candidates import _validate_frozen
from agentfit_ai.solar import AnalysisError

SPEC = ROOT / 'specs/ai-developer/direct-field-comparison'
DEFAULT_OUTPUT = Path('E:/AgentFit/output/direct-field-comparison-v1')
FREE = Path('E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json')


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(output):
    manifest = read_json(SPEC / 'input-manifest.json')
    if manifest['gold_human_reviewed'] is not True:
        raise ValueError('GOLD_NOT_APPROVED')
    source = Path(manifest['input_root'])
    source_paths = {}
    for name in ('document', 'candidate_source', 'equal_grounded_reference', 'saved_response', 'historical_gold'):
        entry = manifest[name]
        path = source / entry['file']
        if digest(path) != entry['sha256']:
            raise ValueError('SOURCE_HASH_MISMATCH')
        source_paths[str(path)] = entry['sha256']
    document = (source / manifest['document']['file']).read_bytes().decode('utf-8')
    frozen = read_json(source / manifest['candidate_source']['file'])['stages']['grounded']
    if frozen != read_json(source / manifest['equal_grounded_reference']['file'])['stages']['grounded']:
        raise ValueError('GROUNDED_MISMATCH')
    if len(document) != 4558 or len(frozen['candidates']) != 68 or len(frozen['rejected']) != 24:
        raise ValueError('INPUT_SIZE_MISMATCH')
    _validate_frozen(document, frozen)
    gold = read_json(SPEC / 'gold.json')
    if gold['human_reviewed'] is not True or len(gold['cases']) != 10:
        raise ValueError('INVALID_GOLD')
    by_id = {c['id']: c for c in frozen['candidates']}
    for g in gold['cases']:
        c = by_id[g['id']]
        if (c['start'], c['end'], document[c['start']:c['end']]) != (g['start'], g['end'], g['value']):
            raise ValueError('GOLD_OCCURRENCE_MISMATCH')
    payloads = {a: [build_payload(a, document, frozen['candidates'][i:i+8])
                    for i in range(0, 68, 8)] for a in ('A', 'B')}
    for a, b in zip(payloads['A'], payloads['B']):
        if a['messages'][1] != b['messages'][1]:
            raise ValueError('CONTEXT_MISMATCH')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'inputs.json', {'document': document, 'frozen': frozen, 'gold': gold})
    write_json(output / 'payloads.json', payloads)
    paths = [*sorted((ROOT / 'ai_service/agentfit_ai').glob('*.py')),
             *sorted(Path(__file__).parent.glob('*.py')), SPEC / 'gold.json', SPEC / 'input-manifest.json',
             output / 'inputs.json', output / 'payloads.json', FREE]
    identity = {str(p.resolve()): digest(p) for p in paths}
    identity.update(source_paths)
    write_json(output / 'freeze.json', {'version': 1, 'sha256': identity,
        'scope': 'one A-then-B pair; classification only', 'max_calls': 18, 'retries': 0,
        'model': MODEL, 'endpoint': ENDPOINT, 'context': 'full document plus each occurrence before/after 240 code points',
        'source_code_points': len(document), 'candidates': 68, 'rejected_preserved': 24,
        'temperature': 0, 'thinking': False, 'max_tokens': 8192,
        'utc': datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'frozen': True, 'output': str(output), 'calls': 0, 'paired_batches': 9}), flush=True)


def projection_score(projection, gold):
    details = []
    # Occurrence-level presence avoids treating another mention as recovery of this one.
    for g in gold:
        if g['field'] is None:
            continue
        evidence = projection['profile']['evidence'][g['field']]
        present = any(e['start'] <= g['start'] and e['end'] >= g['end'] for e in evidence)
        details.append({'id': g['id'], 'present': present,
                        'field_unresolved': g['field'] in projection['unresolvedFields']})
    return {'normal_missing': sum(not d['present'] for d in details), 'details': details}


def run_pair(output, inputs, payloads, gate, sender):
    """One deterministic schedule; dependency injection is for offline tests only."""
    document, frozen, gold = inputs['document'], inputs['frozen'], inputs['gold']['cases']
    expected_ids = [c['id'] for c in frozen['candidates']]
    arms, stopped = {}, False
    for arm in ('A', 'B'):
        if stopped:
            arms[arm] = {'complete': False, 'error': 'NOT_STARTED_AFTER_FAILURE', 'metrics': None,
                         'calls': 0, 'records': []}
            continue
        gate.begin_arm(arm)
        start = time.monotonic()
        records, assessment_records, batches = [], [], []
        local_seconds, error, projection, metrics = 0.0, None, None, None
        try:
            for index, payload in enumerate(payloads[arm]):
                batch = frozen['candidates'][index*8:index*8+8]
                name = 'assessments' if arm == 'A' else 'decisions'
                trace = {}
                print(json.dumps({'arm': arm, 'batch': index+1, 'event': 'starting',
                                  'calls_started': gate.started}), flush=True)
                reply, model, pt, ct = sender._send_payload(payload, (name,), _trace=trace, timeout=600)
                if model != MODEL or set(reply) != {name}:
                    raise ValueError('INVALID_REPLY_ROOT')
                checkpoint = time.monotonic()
                batch_frozen = {'candidates': batch, 'rejected': []}
                if arm == 'A':
                    checked = validate_assessments(document, batch_frozen, reply[name], require_mention_kind=True)
                    assessment_records.extend(checked)
                    normalized = normalize_assessments(document, checked)
                else:
                    normalized = validate_direct(document, batch_frozen, reply[name])
                local_seconds += time.monotonic()-checkpoint
                records.extend(normalized)
                safe_trace = {k: trace.get(k) for k in ('model', 'finish_reason', 'prompt_tokens',
                    'completion_tokens', 'provider_elapsed_ms', 'request_bytes', 'response_bytes')}
                result = {'batch': index+1, 'records': normalized, 'prompt_tokens': pt,
                          'completion_tokens': ct, 'trace': safe_trace}
                batches.append(result)
                write_json(output / f'{arm}-batch-{index+1:02d}.json', result)
                print(json.dumps({'arm': arm, 'batch': index+1, 'event': 'validated',
                                  'records': len(records), 'calls_started': gate.started}), flush=True)
            checkpoint = time.monotonic()
            projection = project_candidate_profile(document, 'direct-field-linkding', frozen,
                                                   projection_labels(records), coverage_verified=False)
            metrics = score_rows(records, gold, expected_ids)
            projected_metrics = projection_score(projection, gold)
            local_seconds += time.monotonic()-checkpoint
        except Exception as exc:
            error = gate.stop_reason or error_code(exc)
            gate.stopped, stopped = True, True
            projected_metrics = None
            # A partial candidate set is never assigned an aggregate score.
            metrics = None
        calls = [c for c in gate.completed if c['arm'] == arm]
        arms[arm] = {'complete': error is None, 'error': error, 'records': records,
            'assessments': assessment_records if arm == 'A' else None, 'metrics': metrics,
            'projection': projection, 'projection_metrics': projected_metrics,
            'calls': sum(1 for p in gate.output.glob(f'*-{arm}-started.json')),
            'responses_returned': sum(c['returned'] for c in calls),
            'provider_failures': sum(not c['returned'] for c in calls), 'retries': 0,
            'model_seconds': sum(c['seconds'] for c in calls),
            'wall_seconds': time.monotonic()-start, 'local_validation_projection_seconds': local_seconds,
            'batches': batches}
        write_json(output / f'{arm}-result.json', arms[arm])
    summary = {'comparable': all(a['complete'] for a in arms.values()),
        'calls_started': gate.started, 'retries': 0, 'arms': arms,
        'free_basis': 'existing unexpired user confirmation; account billing not independently observable',
        'service_applied': False, 'large_goal_resumed': False}
    write_json(output / 'summary.json', summary)
    print(json.dumps({'comparable': summary['comparable'], 'calls_started': gate.started,
                      'errors': {a: r['error'] for a, r in arms.items()}}), flush=True)
    return summary


def live(output):
    frozen_identity = read_json(output / 'freeze.json')
    def check_identity():
        for path, sha in frozen_identity['sha256'].items():
            if digest(path) != sha:
                raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    def check_free():
        scope = validate_free_access(FREE, reserved_calls=18)
        if STREAM_ENDPOINT != ENDPOINT or scope['endpoint'] != ENDPOINT or MODEL not in scope['models']:
            raise ValueError('FREE_ACCESS_UNCONFIRMED')
    check_identity()
    check_free()
    # Exclusive marker prevents budget reset even after a crash/interruption.
    write_json(output / 'live-started.json', {'utc': datetime.now(timezone.utc).isoformat(), 'max_calls': 18})
    key = load_nvidia_key(Path('E:/AgentFit/.env'))
    gate = CallGate(output / 'calls', check_free=check_free, check_identity=check_identity,
                    transport=post_nvidia_streaming)
    return run_pair(output, read_json(output / 'inputs.json'), read_json(output / 'payloads.json'),
                    gate, NvidiaAnalyzer(key, transport=gate, model=MODEL))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('freeze', 'live'))
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze(args.output)
    else:
        result = live(args.output)
        raise SystemExit(0 if result['comparable'] else 1)
