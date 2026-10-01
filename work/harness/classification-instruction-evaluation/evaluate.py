"""Freeze and execute one approved U/U+C pair, stopping on the first failure."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time

_spec = importlib.util.spec_from_file_location('instruction_compare', Path(__file__).with_name('compare.py'))
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)
from agentfit_ai.deepseek_evaluation import ENDPOINT, NvidiaAnalyzer
from agentfit_ai.nvidia_evaluation_inputs import validate_free_access, load_nvidia_key
from agentfit_ai.nvidia_streaming import post_nvidia_streaming, ENDPOINT as STREAM_ENDPOINT

ROOT, MODEL, write_json = compare.ROOT, compare.MODEL, compare.write_json
SPEC = ROOT / 'specs/ai-developer/classification-instruction-evaluation'
FREE = Path('E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json')
OUTPUT = Path('E:/AgentFit/output/classification-instruction-v1')


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_free(path):
    scope = validate_free_access(path, reserved_calls=8)
    if scope['endpoint'] != ENDPOINT or STREAM_ENDPOINT != ENDPOINT or MODEL not in scope['models']:
        raise ValueError('FREE_ACCESS_UNCONFIRMED')


def check_identity(identity):
    for path, sha in identity.items():
        if digest(path) != sha:
            raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')


def prepare_package(spec_dir):
    spec_dir = Path(spec_dir)
    sources, inputs = read_json(spec_dir/'sources.json'), read_json(spec_dir/'candidates-draft.json')
    all_gold = read_json(spec_dir/'gold-draft.json')['cases']
    guidance = (spec_dir/'classification-guidance-draft.txt').read_bytes().decode('utf-8')
    if hashlib.sha256(guidance.encode('utf-8')).hexdigest() != read_json(spec_dir/'preparation-checks.json')['classification_guidance_sha256']:
        raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    documents, jobs = {}, []
    if [d['docId'] for d in inputs['documents']] != ['FR', 'LS']:
        raise ValueError('INVALID_DOCUMENTS')
    for doc in inputs['documents']:
        doc_id, frozen = doc['docId'], doc['frozen']
        document = (spec_dir/doc['sourceFile']).read_bytes().decode('utf-8')
        source = next(d for d in sources['documents'] if d['id'] == doc_id)
        if hashlib.sha256(document.encode('utf-8')).hexdigest() != doc['sourceSha256'] or doc['sourceSha256'] != source['files']['README.md']['sha256']:
            raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
        gold = [g for g in all_gold if g['docId'] == doc_id]
        if len(gold) != 16 or len(frozen['candidates']) != 16 or sum(g['scored'] for g in gold) != 15:
            raise ValueError('INVALID_GOLD')
        by_id = {g['candidateId']: g for g in gold}
        for c in frozen['candidates']:
            g = by_id[c['id']]
            if document[c['start']:c['end']] != g['quote'] or g['span'] != {k:c[k] for k in ('start','end')}:
                raise ValueError('INVALID_GOLD')
        pair = compare.build_instruction_pair(document, frozen, guidance)
        documents[doc_id] = {'document': document, 'frozen': frozen, 'gold': gold, 'pair': pair}
        order = ('U', 'U+C') if doc_id == 'FR' else ('U+C', 'U')
        for arm in order:
            for i, payload in enumerate(pair['payloads'][arm]):
                jobs.append({'docId': doc_id, 'arm': arm, 'batch': i+1, 'payload': payload})
    if len(jobs) != 8 or sum(g['scored'] and g['expectedStatus']=='confirmed' for g in all_gold) != 16:
        raise ValueError('INVALID_GOLD')
    return {'documents': documents, 'jobs': jobs}


def freeze(output, *, spec_dir=SPEC, free=FREE):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    check_free(free)
    package = prepare_package(spec_dir)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'package.json', package)
    write_json(output/'approval.json', {'approved_by': 'user', 'utc': datetime.now(timezone.utc).isoformat(),
        'source_plan_commit': 'b35b2c9', 'scope': 'one U/U+C pair, fixed guidance and gold; no service or goal resume',
        'scored_cases': 30, 'separate_review_cases': ['FR16', 'LS15'], 'max_calls': 8, 'retries': 0})
    paths = [*sorted((ROOT/'ai_service/agentfit_ai').glob('*.py')),
             *sorted(Path(__file__).parent.glob('*.py')),
             ROOT/'work/harness/b-evidence-selection-comparison/experiment.py',
             ROOT/'work/harness/direct-field-comparison/comparison.py',
             ROOT/'work/harness/evidence-relation-repair/source_registry.py',
             ROOT/'work/harness/evidence-relation-repair/legacy_audit.py',
             *[p for p in Path(spec_dir).rglob('*') if p.is_file()],
             Path(free), output/'package.json', output/'approval.json',
             ROOT/'ai_service/tests/test_classification_instruction_evaluation.py']
    record = {'version':'classification-instruction-v1','sha256':{str(p.resolve()):digest(p) for p in paths},
        'model': MODEL, 'endpoint':ENDPOINT,'max_calls':8,'retries':0,'batch_size':8,
        'timeout_seconds':600,'overall_timeout_seconds':5400,'temperature':0,'thinking':False,
        'max_tokens':8192,'free_record':str(Path(free).resolve()),'utc':datetime.now(timezone.utc).isoformat()}
    write_json(output/'freeze.json', record)
    print(json.dumps({'frozen':True,'files':len(record['sha256']),'calls':0,'max_calls':8}), flush=True)
    return record


def run_package(output, package, gate, sender):
    output = Path(output)
    results = {doc:{arm:{'records':[],'evidence':[],'batches':[],'usage':[],'wall_seconds':0.0}
               for arm in ('U','U+C')} for doc in package['documents']}
    stop_error = None
    for job in package['jobs']:
        if gate.stopped:
            break
        doc_id, arm, number = job['docId'], job['arm'], job['batch']
        source, result = package['documents'][doc_id], results[doc_id][arm]
        start = time.monotonic()
        before_calls = gate.started
        trace = {}
        print(json.dumps({'doc':doc_id,'arm':arm,'batch':number,'event':'starting','calls':gate.started}),flush=True)
        try:
            reply, model, pt, ct = sender._send_payload(job['payload'], ('decisions',), _trace=trace, timeout=600)
            if model != MODEL or set(reply) != {'decisions'}:
                raise ValueError('INVALID_REPLY_ROOT')
            # Preserve parsed raw output before normalization as well as transport response.
            write_json(output/f'{doc_id}-{arm}-{number:02d}-parsed.json', reply)
            batch = source['frozen']['candidates'][(number-1)*8:number*8]
            rows, evidence = compare.baseline.normalize('U', source['document'], source['pair']['registry'],
                                                       batch, reply['decisions'])
            result['records'].extend(rows)
            result['evidence'].extend(evidence)
            data = {'batch':number,'records':rows,'evidence':evidence,'prompt_tokens':pt,'completion_tokens':ct,
                    'trace':{k:trace.get(k) for k in ('model','finish_reason','provider_elapsed_ms','request_bytes','response_bytes')}}
            result['batches'].append(data)
            write_json(output/f'{doc_id}-{arm}-{number:02d}-validated.json',data)
            print(json.dumps({'doc':doc_id,'arm':arm,'batch':number,'event':'validated','calls':gate.started}),flush=True)
        except Exception as exc:
            stop_error = gate.stop_reason or compare.safe_error(exc)
            gate.stopped, gate.stop_reason = True, stop_error
        finally:
            result['wall_seconds'] += time.monotonic()-start
            if gate.started > before_calls:
                # Trace usage survives parsing/normalization failure. Missing usage stays unknown.
                result['usage'].append({'sequence':gate.started, 'batch':number,
                    'prompt_tokens':trace.get('prompt_tokens'),
                    'completion_tokens':trace.get('completion_tokens')})
    for doc_id, arms in results.items():
        for arm, result in arms.items():
            result['metrics'] = compare.score_instruction_rows(result['records'], result['evidence'], package['documents'][doc_id]['gold'])
            calls = [c for c in gate.completed if (c['docId'],c['arm'])==(doc_id,arm)]
            result.update(complete=result['metrics']['complete'],calls=len(calls),
                responses_returned=sum(c['returned'] for c in calls),
                provider_failures=sum(not c['returned'] for c in calls),
                model_seconds=sum(c['seconds'] for c in calls))
            for key in ('prompt_tokens','completion_tokens'):
                known = [u[key] for u in result['usage'] if type(u[key]) is int and u[key] >= 0]
                unknown = len(result['usage'])-len(known)
                result[key] = None if unknown else sum(known)
                result[key+'_known_sum'] = sum(known)
                result[key+'_unknown_calls'] = unknown
    report={'documents':results,'comparable':stop_error is None and all(a['complete'] for d in results.values() for a in d.values()),
        'stop_error':stop_error,'calls_started':gate.started,'retries':0,'unstarted_calls':8-gate.started,
        'free_basis':'unexpired human account confirmation; no independent billing/quota inspection',
        'service_applied':False,'large_goal_resumed':False}
    write_json(output/'summary.json',report)
    print(json.dumps({'comparable':report['comparable'],'calls':gate.started,'stop_error':stop_error}),flush=True)
    return report


def live(output):
    output = Path(output)
    if (output/'live-started.json').exists():
        raise FileExistsError(output/'live-started.json')
    frozen = read_json(output/'freeze.json')
    identity = dict(frozen['sha256'])
    identity[str((output/'freeze.json').resolve())] = digest(output/'freeze.json')
    free = Path(frozen['free_record'])
    check_identity(identity)
    check_free(free)
    # Exclusive durable marker makes re-running after an interruption impossible.
    write_json(output/'live-started.json',{'utc':datetime.now(timezone.utc).isoformat(),
                                         'max_calls':8,'retries':0,'freeze_sha256':digest(output/'freeze.json')})
    package = read_json(output/'package.json')
    key = load_nvidia_key(Path('E:/AgentFit/.env'))
    gate = compare.EightCallGate(output/'calls',package['jobs'],check_free=lambda:check_free(free),
        check_identity=lambda:check_identity(identity),transport=post_nvidia_streaming)
    report = run_package(output, package, gate, NvidiaAnalyzer(key,transport=gate,model=MODEL))
    check_identity(identity)
    write_json(output/'verification.json',{'frozen_files_unchanged':True,'files':len(identity),
        'calls_started':gate.started,'retries':0,'service_applied':False,'large_goal_resumed':False})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','live'))
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze(args.output)
    else:
        result = live(args.output)
        raise SystemExit(0 if result['comparable'] else 1)
