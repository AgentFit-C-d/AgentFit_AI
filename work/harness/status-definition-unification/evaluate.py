"""One status-only UC/US pair. No retries, fail closed, exclusive result writes."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time

_spec = importlib.util.spec_from_file_location('status_experiment',Path(__file__).with_name('experiment.py'))
experiment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(experiment)
previous, compare = experiment.previous, experiment.compare
ROOT, SPEC, MODEL, ARMS = experiment.ROOT, experiment.SPEC, experiment.MODEL, experiment.ARMS
read_json, digest, write_json = previous.read_json, previous.digest, previous.write_json
PRIOR = Path('E:/AgentFit/output/classification-instruction-v1')
OUTPUT = Path('E:/AgentFit/output/status-definition-v1')


def load_prior():
    frozen = read_json(PRIOR/'freeze.json')
    previous.check_identity(frozen['sha256'])
    if digest(PRIOR/'freeze.json') != read_json(PRIOR/'live-started.json')['freeze_sha256']:
        raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    prior = read_json(PRIOR/'package.json')
    for i,job in enumerate(prior['jobs'],1):
        if json.dumps(read_json(PRIOR/'calls'/f'{i:02d}-request.json')) != json.dumps(job['payload']):
            raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    return prior, frozen


def freeze(output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    previous.check_free(previous.FREE)
    prior, old_freeze = load_prior()
    package = experiment.prepare_package(prior)
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/'package.json',package)
    write_json(output/'approval.json',{'approved_by':'user','utc':datetime.now(timezone.utc).isoformat(),
        'scope':'status definitions only; one UC/US pair; no service or goal resume',
        'scored_cases':30,'separate_cases':['FR16','LS15'],'max_calls':8,'retries':0})
    identity = dict(old_freeze['sha256'])
    paths = [PRIOR/'freeze.json',PRIOR/'live-started.json',*sorted((PRIOR/'calls').glob('*.json')),
             *sorted(Path(__file__).parent.glob('*.py')),*sorted(SPEC.glob('*')),
             output/'package.json',output/'approval.json',ROOT/'ai_service/tests/test_status_definition_unification.py']
    identity.update({str(p.resolve()):digest(p) for p in paths if p.is_file()})
    record = {'version':'status-definition-v1','sha256':identity,'model':MODEL,'endpoint':previous.ENDPOINT,
        'free_record':str(previous.FREE),'max_calls':8,'retries':0,'timeout_seconds':600,
        'overall_timeout_seconds':5400,'utc':datetime.now(timezone.utc).isoformat()}
    write_json(output/'freeze.json',record)
    print(json.dumps({'frozen':True,'files':len(identity),'calls':0}),flush=True)
    return record


def run_package(output,package,gate,sender):
    output = Path(output)
    results = {doc:{arm:{'records':[],'evidence':[],'batches':[],'usage':[],'wall_seconds':0.0}
                   for arm in ARMS} for doc in package['documents']}
    stop_error = None
    for job in package['jobs']:
        if gate.stopped:
            break
        doc_id,arm,number = job['docId'],job['arm'],job['batch']
        source,result = package['documents'][doc_id],results[doc_id][arm]
        start,before,trace = time.monotonic(),gate.started,{}
        print(json.dumps({'doc':doc_id,'arm':arm,'batch':number,'event':'starting','calls':gate.started}),flush=True)
        try:
            reply,model,pt,ct = sender._send_payload(job['payload'],('decisions',),_trace=trace,timeout=600)
            if model != MODEL or set(reply) != {'decisions'}:
                raise ValueError('INVALID_REPLY_ROOT')
            write_json(output/f'{doc_id}-{arm}-{number:02d}-parsed.json',reply)
            batch = source['frozen']['candidates'][(number-1)*8:number*8]
            rows,evidence = compare.baseline.normalize('U',source['document'],source['pair']['registry'],batch,reply['decisions'])
            result['records'].extend(rows)
            result['evidence'].extend(evidence)
            data = {'batch':number,'records':rows,'evidence':evidence,'prompt_tokens':pt,'completion_tokens':ct,
                    'trace':{k:trace.get(k) for k in ('model','finish_reason','provider_elapsed_ms','request_bytes','response_bytes')}}
            result['batches'].append(data)
            write_json(output/f'{doc_id}-{arm}-{number:02d}-validated.json',data)
            print(json.dumps({'doc':doc_id,'arm':arm,'batch':number,'event':'validated','calls':gate.started}),flush=True)
        except Exception as exc:
            stop_error = gate.stop_reason or compare.safe_error(exc)
            gate.stopped,gate.stop_reason = True,stop_error
        finally:
            result['wall_seconds'] += time.monotonic()-start
            if gate.started > before:
                result['usage'].append({'sequence':gate.started,'batch':number,
                    'prompt_tokens':trace.get('prompt_tokens'),'completion_tokens':trace.get('completion_tokens')})
    for doc_id,arms in results.items():
        source = package['documents'][doc_id]
        for arm,result in arms.items():
            result['metrics'] = compare.score_instruction_rows(result['records'],result['evidence'],source['gold'])
            result['diagnostics'] = experiment.diagnostics(result['records'],source['gold'],source['document'])
            calls = [c for c in gate.completed if (c['docId'],c['arm'])==(doc_id,arm)]
            result.update(complete=result['metrics']['complete'],calls=len(calls),
                responses_returned=sum(c['returned'] for c in calls),provider_failures=sum(not c['returned'] for c in calls),
                model_seconds=sum(c['seconds'] for c in calls))
            for key in ('prompt_tokens','completion_tokens'):
                known = [u[key] for u in result['usage'] if type(u[key]) is int and u[key]>=0]
                unknown = len(result['usage'])-len(known)
                result[key] = None if unknown else sum(known)
                result[key+'_known_sum'],result[key+'_unknown_calls'] = sum(known),unknown
    report = {'documents':results,'arm_labels':package['arm_labels'],
        'comparable':stop_error is None and all(a['complete'] for d in results.values() for a in d.values()),
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
    previous.check_identity(identity)
    previous.check_free(free)
    write_json(output/'live-started.json',{'utc':datetime.now(timezone.utc).isoformat(),
        'max_calls':8,'retries':0,'freeze_sha256':digest(output/'freeze.json')})
    package = read_json(output/'package.json')
    key = previous.load_nvidia_key(Path('E:/AgentFit/.env'))
    gate = compare.EightCallGate(output/'calls',package['jobs'],check_free=lambda:previous.check_free(free),
        check_identity=lambda:previous.check_identity(identity),transport=previous.post_nvidia_streaming)
    report = run_package(output,package,gate,previous.NvidiaAnalyzer(key,transport=gate,model=MODEL))
    previous.check_identity(identity)
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
        raise SystemExit(0 if live(args.output)['comparable'] else 1)
