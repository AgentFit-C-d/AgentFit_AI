"""Execute the approved model-only pair once. Failure is terminal; never tune or retry."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time

_spec=importlib.util.spec_from_file_location('status_model_experiment',Path(__file__).with_name('experiment.py'))
experiment=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(experiment)
ROOT,SPEC=experiment.ROOT,experiment.SPEC
MODELS,ARMS=experiment.MODELS,experiment.ARMS
compare,status=experiment.compare,experiment.status
previous=status.previous
read_json,digest,write_json=previous.read_json,previous.digest,previous.write_json
PRIOR=Path('E:/AgentFit/output/status-definition-v1')
OUTPUT=Path('E:/AgentFit/output/status-model-comparison-v1')


def load_saved():
    manifest=read_json(SPEC/'input-freeze.json')
    previous.check_identity(manifest['sha256'])
    old=read_json(PRIOR/'freeze.json')
    previous.check_identity(old['sha256'])  # Historical integrity only; NEVER free authorization.
    saved=read_json(PRIOR/'package.json')
    for i,job in enumerate(saved['jobs'],1):
        if job['arm']=='US' and json.dumps(read_json(PRIOR/'calls'/f'{i:02d}-request.json'))!=json.dumps(job['payload']):
            raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    return saved,dict(old['sha256']) | manifest['sha256']


def freeze(output,free):
    output,free=Path(output),Path(free)
    if output.exists():
        raise FileExistsError(output)
    experiment.check_free(free)
    saved,identity=load_saved()
    package=experiment.build_model_pair(saved)
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/'package.json',package)
    write_json(output/'approval.json',{
        'approved_by':'user','utc':datetime.now(timezone.utc).isoformat(),
        'scope':'fixed US, 32 candidates, model only; first GLM production batch also checks compatibility',
        'max_calls':8,'retries':0,'service_applied':False,'large_goal_resumed':False})
    paths=[PRIOR/'freeze.json',SPEC/'input-freeze.json',free,output/'package.json',output/'approval.json',
           *sorted(SPEC.glob('*')),*sorted(Path(__file__).parent.glob('*.py')),
           ROOT/'ai_service/tests/test_status_model_comparison.py']
    identity.update({str(p.resolve()):digest(p) for p in paths if p.is_file()})
    record={'version':'status-model-comparison-v1','sha256':identity,'free_record':str(free.resolve()),
            'models':MODELS,'endpoint':experiment.ENDPOINT,'max_calls':8,'retries':0,
            'timeout_seconds':600,'overall_timeout_seconds':5400,'utc':datetime.now(timezone.utc).isoformat()}
    write_json(output/'freeze.json',record)
    print(json.dumps({'frozen':True,'files':len(identity),'calls':0}),flush=True)
    return record


def run_package(output,package,gate,sender):
    output=Path(output)
    started=time.monotonic()
    results={doc:{arm:{'records':[],'evidence':[],'batches':[],'usage':[],'wall_seconds':0.0}
             for arm in ARMS} for doc in package['documents']}
    stop_error=None
    for job in package['jobs']:
        if gate.stopped:
            break
        doc,arm,batch=job['docId'],job['arm'],job['batch']
        source,result=package['documents'][doc],results[doc][arm]
        start,before,trace=time.monotonic(),gate.started,{}
        print(json.dumps({'doc':doc,'arm':arm,'batch':batch,'event':'starting','calls':gate.started}),flush=True)
        try:
            reply,model,pt,ct=sender._send_payload(job['payload'],('decisions',),_trace=trace,timeout=600)
            if model!=MODELS[arm] or set(reply)!={'decisions'}:
                raise ValueError('INVALID_REPLY_ROOT')
            write_json(output/f'{doc}-{arm}-{batch:02d}-parsed.json',reply)
            candidates=source['frozen']['candidates'][(batch-1)*8:batch*8]
            records,evidence=compare.baseline.normalize('U',source['document'],source['pair']['registry'],candidates,reply['decisions'])
            result['records'].extend(records)
            result['evidence'].extend(evidence)
            data={'batch':batch,'records':records,'evidence':evidence,'prompt_tokens':pt,'completion_tokens':ct,
                  'trace':{k:trace.get(k) for k in ('model','finish_reason','provider_elapsed_ms','request_bytes','response_bytes')}}
            result['batches'].append(data)
            write_json(output/f'{doc}-{arm}-{batch:02d}-validated.json',data)
            print(json.dumps({'doc':doc,'arm':arm,'batch':batch,'event':'validated','calls':gate.started}),flush=True)
        except Exception as exc:
            stop_error=gate.stop_reason or compare.safe_error(exc)
            gate.stopped,gate.stop_reason=True,stop_error
        finally:
            result['wall_seconds']+=time.monotonic()-start
            if gate.started>before:
                result['usage'].append({'sequence':gate.started,'batch':batch,
                    'prompt_tokens':trace.get('prompt_tokens'),'completion_tokens':trace.get('completion_tokens')})
    for doc,arms in results.items():
        source=package['documents'][doc]
        for arm,result in arms.items():
            metrics=compare.score_instruction_rows(result['records'],result['evidence'],source['gold'])
            result.update(metrics=metrics,complete=metrics['complete'],
                          comparison_metrics=metrics if metrics['complete'] else None,
                          diagnostics=status.diagnostics(result['records'],source['gold'],source['document']))
            calls=[c for c in gate.completed if (c['docId'],c['arm'])==(doc,arm)]
            seconds=[c['seconds'] for c in calls]
            result.update(calls=len(calls),responses_returned=sum(c['returned'] for c in calls),
                          provider_failures=sum(not c['returned'] for c in calls),
                          model_seconds=sum(seconds),mean_call_seconds=sum(seconds)/len(seconds) if seconds else None,
                          max_call_seconds=max(seconds) if seconds else None)
            for key in ('prompt_tokens','completion_tokens'):
                known=[u[key] for u in result['usage'] if type(u[key]) is int and u[key]>=0]
                unknown=len(result['usage'])-len(known)
                result[key]=None if unknown else sum(known)
                result[key+'_known_sum'],result[key+'_unknown_calls']=sum(known),unknown
    report={'documents':results,'arm_labels':dict(MODELS),'calls_started':gate.started,
            'retries':0,'unstarted_calls':8-gate.started,'stop_error':stop_error,
            'comparable':stop_error is None and all(a['complete'] for d in results.values() for a in d.values()),
            'wall_seconds':time.monotonic()-started,
            'free_basis':'fresh user confirmation for these free endpoints and this eight-attempt run; no independent account quota inspection',
            'option_enforcement':'request acceptance and schema-valid content observable; backend enforcement of individual options not independently observable',
            'response_storage':'existing SSE transport assembled content envelope; raw field/status retained; not original SSE event bytes',
            'service_applied':False,'large_goal_resumed':False}
    write_json(output/'summary.json',report)
    print(json.dumps({'comparable':report['comparable'],'calls':gate.started,'stop_error':stop_error}),flush=True)
    return report


def live(output):
    output=Path(output)
    if (output/'live-started.json').exists():
        raise FileExistsError(output/'live-started.json')
    frozen=read_json(output/'freeze.json')
    identity=dict(frozen['sha256'])
    identity[str((output/'freeze.json').resolve())]=digest(output/'freeze.json')
    free=Path(frozen['free_record'])
    previous.check_identity(identity)
    experiment.check_free(free)
    write_json(output/'live-started.json',{'utc':datetime.now(timezone.utc).isoformat(),
               'max_calls':8,'retries':0,'freeze_sha256':digest(output/'freeze.json')})
    package=read_json(output/'package.json')
    key=previous.load_nvidia_key(Path('E:/AgentFit/.env'))
    gate=experiment.ModelCallGate(output/'calls',package['jobs'],check_free=lambda:experiment.check_free(free),
         check_identity=lambda:previous.check_identity(identity),transport=previous.post_nvidia_streaming)
    report=run_package(output,package,gate,experiment.FixedPayloadSender(key,gate))
    previous.check_identity(identity)
    write_json(output/'verification.json',{'frozen_files_unchanged':True,'files':len(identity),
               'calls_started':gate.started,'retries':0,'service_applied':False,'large_goal_resumed':False})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','live'))
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--free',type=Path)
    args=parser.parse_args()
    if args.command=='freeze':
        if args.free is None: parser.error('--free required')
        freeze(args.output,args.free)
    else:
        raise SystemExit(0 if live(args.output)['comparable'] else 1)
