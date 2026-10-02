"""One new LS-only four-call comparison. No retries, no model-specific tuning."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'ai_service'))
_spec = importlib.util.spec_from_file_location('localsend_fixed_comparison_base',
    ROOT/'work/harness/status-model-comparison/evaluate.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
SPEC = ROOT/'specs/ai-developer/localsend-model-comparison'
PRIOR = Path('E:/AgentFit/output/status-model-comparison-v1')
OUTPUT = Path('E:/AgentFit/output/localsend-model-comparison-v1')
SCHEDULE = (('LS','D',1), ('LS','G',1), ('LS','G',2), ('LS','D',2))
FREE_BASIS = ('User confirmed these NVIDIA endpoints are free and authorized this new LS-only four-call run; '
              'no independent account quota inspection; no paid fallback, no retry.')


class LocalSendGate(base.experiment.ModelCallGate):
    schedule = SCHEDULE
    max_calls = 4
    free_basis = FREE_BASIS


def localsend_package(prior):
    source = deepcopy(prior['documents']['LS'])
    jobs = deepcopy([j for j in prior['jobs'] if j['docId']=='LS'])
    if (len(source['frozen']['candidates']) != 16 or len(source['gold']) != 16 or
            [(j['docId'],j['arm'],j['batch']) for j in jobs] != list(SCHEDULE)):
        raise ValueError('INVALID_LS_PACKAGE')
    for job in jobs:
        if job['payload'] != source['pair']['payloads'][job['arm']][job['batch']-1]:
            raise ValueError('PAYLOAD_CHANGED')
    return {'documents': {'LS': source}, 'jobs': jobs, 'arm_labels': dict(base.MODELS)}


def approval(now):
    return {'version':'localsend-model-free-v1', 'confirmed_by':'user',
        'confirmed_at':now.isoformat(), 'expires_at':(now+timedelta(minutes=90)).isoformat(),
        'confirmed_no_additional_charge':True, 'no_paid_fallback':True,
        'endpoint':base.experiment.ENDPOINT, 'models':list(base.MODELS.values()),
        'max_calls':4, 'retries':0, 'documents':['LS'], 'basis':FREE_BASIS,
        'expiry_basis':'Conservative local cutoff for this newly authorized run, not a provider trial expiry.',
        'independent_account_quota_inspection':False, 'old_call_budget_reused':False}


def check_approval(path, *, now=None):
    try:
        record=base.read_json(path)
        now=now or datetime.now(timezone.utc)
        start=datetime.fromisoformat(record['confirmed_at'])
        end=datetime.fromisoformat(record['expires_at'])
        valid=(record['version']=='localsend-model-free-v1' and record['confirmed_by']=='user'
            and record['confirmed_no_additional_charge'] is True and record['no_paid_fallback'] is True
            and record['endpoint']==base.experiment.ENDPOINT and sorted(record['models'])==sorted(base.MODELS.values())
            and type(record['max_calls']) is int and record['max_calls']==4
            and type(record['retries']) is int and record['retries']==0 and record['documents']==['LS']
            and start.tzinfo is not None and end.tzinfo is not None and start<=now<end
            and 0<(end-start).total_seconds()<=5400)
        remaining=(end-now).total_seconds()
    except (ValueError,TypeError,KeyError,OSError):
        valid=False
    if not valid:
        raise ValueError('FREE_ACCESS_UNCONFIRMED')
    return remaining


def git(*args):
    return subprocess.run(['rtk','proxy','git','-c',f'safe.directory={ROOT.as_posix()}',*args],
        cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout.decode('utf-8').strip()


def freeze(output):
    output=Path(output)
    if output.exists():
        raise FileExistsError(output)
    # No production/parser/prompt/model settings changed since the diagnostic commit.
    if git('diff','f0bdc04','--','ai_service/agentfit_ai'):
        raise ValueError('SERVICE_SOURCE_CHANGED')
    # Historical integrity check: only the previously approved diagnostic transport and
    # the LS schedule/report wiring may differ from the previous experiment.
    old=base.read_json(PRIOR/'freeze.json')['sha256']
    allowed={str((ROOT/p).resolve()) for p in (
        'ai_service/agentfit_ai/nvidia_streaming.py','ai_service/agentfit_ai/nvidia_stream_worker.py',
        'work/harness/status-model-comparison/experiment.py','work/harness/status-model-comparison/evaluate.py')}
    base.previous.check_identity({p:d for p,d in old.items() if p not in allowed})
    package=localsend_package(base.read_json(PRIOR/'package.json'))
    # All model differences were already frozen; this run reuses exact saved payloads.
    if package['documents']['LS'] != base.read_json(PRIOR/'package.json')['documents']['LS']:
        raise ValueError('LS_INPUT_CHANGED')
    output.mkdir(parents=True,exist_ok=False)
    base.write_json(output/'package.json',package)
    base.write_json(output/'approval.json',approval(datetime.now(timezone.utc)))
    check_approval(output/'approval.json')
    paths={Path(p) for p in old}
    paths.update((ROOT/'ai_service/agentfit_ai').glob('*.py'))
    paths.update(Path(__file__).parent.glob('*.py'))
    paths.update(SPEC.glob('*.md'))
    paths.update((PRIOR/'freeze.json',PRIOR/'package.json',output/'package.json',output/'approval.json',
                  ROOT/'ai_service/tests/test_localsend_model_comparison.py'))
    identity={str(p.resolve()):base.digest(p) for p in sorted(paths) if p.is_file()}
    record={'version':'localsend-model-comparison-v1','git_commit':git('rev-parse','HEAD'),
        'diagnostic_base_commit':'f0bdc04','sha256':identity,'max_calls':4,'retries':0,
        'schedule':SCHEDULE,'models':base.MODELS,'endpoint':base.experiment.ENDPOINT,
        'timeout_seconds':600,'overall_timeout_seconds':5400,
        'preserved_prior_files':{str(p.resolve()):base.digest(p) for p in PRIOR.rglob('*') if p.is_file()},
        'service_applied':False,'large_goal_resumed':False}
    base.write_json(output/'freeze.json',record)
    print(json.dumps({'frozen':True,'files':len(identity),'git_commit':record['git_commit'],'model_calls':0}),flush=True)


def live(output):
    output=Path(output)
    marker=output/'live-started.json'
    if marker.exists():
        raise FileExistsError(marker)
    frozen=base.read_json(output/'freeze.json')
    identity=dict(frozen['sha256'])
    identity[str((output/'freeze.json').resolve())]=base.digest(output/'freeze.json')
    base.previous.check_identity(identity)
    check_approval(output/'approval.json')
    base.write_json(marker,{'max_calls':4,'retries':0,'utc':datetime.now(timezone.utc).isoformat(),
                           'freeze_sha256':base.digest(output/'freeze.json')})
    package=base.read_json(output/'package.json')
    key=base.previous.load_nvidia_key(Path('E:/AgentFit/.env'))
    gate=LocalSendGate(output/'calls',package['jobs'],
        check_identity=lambda:base.previous.check_identity(identity),
        check_free=lambda:check_approval(output/'approval.json'),transport=base.previous.post_nvidia_streaming)
    report=base.run_package(output,package,gate,base.experiment.FixedPayloadSender(key,gate))
    base.previous.check_identity(identity)
    base.previous.check_identity(frozen['preserved_prior_files'])
    base.write_json(output/'verification.json',{'frozen_files_unchanged':True,'files':len(identity),
        'prior_results_unchanged':True,'calls_started':gate.started,'retries':0,
        'diagnostic_failures':[r for r in gate.completed if r['error'] is not None],
        'service_applied':False,'large_goal_resumed':False})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','live'))
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    if args.command=='freeze':
        freeze(args.output)
    else:
        raise SystemExit(0 if live(args.output)['comparable'] else 1)
