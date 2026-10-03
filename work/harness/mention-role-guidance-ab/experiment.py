"""Approved two-call role-guidance comparison; never imported by the service."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'ai_service'))
from agentfit_ai.candidate_semantic_assessment import assessment_payload, validate_assessments
from agentfit_ai.candidate_mention_roles import MENTION_ROLE_INSTRUCTION
from agentfit_ai.deepseek_evaluation import MODEL, ENDPOINT, NvidiaAnalyzer, nvidia_payload, load_key
from agentfit_ai.nvidia_streaming import post_nvidia_streaming
from agentfit_ai.solar import AnalysisError, _reject_sensitive
from diagnostic_tools.document_profile_live import actual_hashes, save, digest

PRIOR = Path('E:/AgentFit/output/document-profile-v3-live-20261002-v1')
PLAN = ROOT/'specs/ai-developer/mention-role-cause-analysis/comparison-plan.md'
OUTPUT = Path('E:/AgentFit/output/mention-role-guidance-ab-20261003-v1')
IDS = ('C000','C002','C003','C043','C081','C091','C125','C145')
POSITIONS = ((2,10),(137,142),(168,176),(1857,1863),(3570,3576),(4020,4025),(5122,5128),(7266,7274))
EXPECTED = (
    ('project_name','other'), ('project_type','other'), ('project_name','other'),
    ('external_integrations','external_service'), ('external_integrations','external_service'),
    ('other','other'), ('external_integrations','external_service'), ('project_name','other'))
ALLOWED_ENDPOINT = 'https://integrate.api.nvidia.com/v1/chat/completions'
ALLOWED_MODEL = 'deepseek-ai/deepseek-v4.1-flash'
SOURCE_SHA = '9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451'
GOLD_SHA = '40ecc131c19fb8aa0e0127b67f9a5adf95885ed194a67350d3c89a9e9b328260'
TOTAL_SECONDS, REQUEST_SECONDS, FINISH_RESERVE = 1220, 600, 20


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build_package():
    document = (PRIOR/'document.txt').read_bytes().decode('utf-8')
    if sha(document.encode('utf-8')) != SOURCE_SHA or digest(PRIOR/'gold.json') != GOLD_SHA:
        raise ValueError('INPUT_CHANGED')
    trace = read(PRIOR/'trace.json')
    candidates = [deepcopy(c) for c in trace['stages']['grounded']['candidates'] if c['id'] in IDS]
    if (tuple(c['id'] for c in candidates) != IDS or
            tuple((c['start'], c['end']) for c in candidates) != POSITIONS):
        raise ValueError('CANDIDATES_CHANGED')
    block = re.findall(r'```text\r?\n(.*?)\r?\n```', PLAN.read_bytes().decode('utf-8'), flags=re.S)
    if len(block) != 1:
        raise ValueError('PLAN_BLOCK_AMBIGUOUS')
    replacement = block[0].replace('\r\n', '\n')
    a = nvidia_payload(assessment_payload(document, candidates), model=MODEL)
    previous = trace['calls'][3]['request']
    options = lambda p: {k:v for k,v in p.items() if k not in ('messages','response_format')}
    if options(a) != options(previous) or a['messages'][0] != previous['messages'][0]:
        raise ValueError('BASELINE_OPTIONS_OR_INSTRUCTIONS_CHANGED')
    if a['messages'][0]['content'].count(MENTION_ROLE_INSTRUCTION) != 1:
        raise ValueError('ROLE_BLOCK_AMBIGUOUS')
    b = deepcopy(a)
    b['messages'][0]['content'] = a['messages'][0]['content'].replace(MENTION_ROLE_INSTRUCTION, replacement)
    package = {'document': document, 'frozen': {'candidates': candidates, 'rejected': []},
        'payloads': {'A':a, 'B':b}, 'roleBlocks': {'A':MENTION_ROLE_INSTRUCTION, 'B':replacement},
        'expected': [{'id':cid, 'field':field, 'mentionKind':kind,
                      'modelStatus':'irrelevant' if field=='other' else 'confirmed'}
                     for cid,(field,kind) in zip(IDS,EXPECTED)]}
    verify_pair(package)
    return package


def verify_pair(package):
    a,b = deepcopy(package['payloads']['A']),deepcopy(package['payloads']['B'])
    for arm,payload in (('A',a),('B',b)):
        block = package['roleBlocks'][arm]
        if payload['messages'][0]['content'].count(block) != 1:
            raise ValueError('ROLE_BLOCK_CHANGED')
        payload['messages'][0]['content'] = payload['messages'][0]['content'].replace(block,'ROLE_BLOCK_ONLY')
        data = json.loads(payload['messages'][1]['content'])
        if set(data) != {'document','candidates'} or data['document'] != package['document']:
            raise ValueError('MODEL_INPUT_CHANGED')
        for sent,c in zip(data['candidates'],package['frozen']['candidates'], strict=True):
            start,end=c['start'],c['end']
            expected = {**c, 'value':package['document'][start:end],
                        'before':package['document'][max(0,start-240):start],
                        'after':package['document'][end:end+240]}
            if sent != expected:
                raise ValueError('CANDIDATE_CONTEXT_CHANGED')
    if a != b or a['model'] != ALLOWED_MODEL or ENDPOINT != ALLOWED_ENDPOINT:
        raise ValueError('PAIR_HAS_OTHER_DIFFERENCES')


def identity():
    hashes = {str(ROOT/p):h for p,h in actual_hashes().items()}
    paths = list(Path(__file__).parent.glob('*.py')) + [PLAN, PRIOR/'trace.json', PRIOR/'document.txt', PRIOR/'gold.json']
    hashes.update({str(p.resolve()):digest(p) for p in paths})
    return hashes


def check_identity(hashes):
    if any(digest(Path(p)) != expected for p,expected in hashes.items()):
        raise ValueError('FROZEN_FILE_CHANGED')


def freeze(output):
    package=build_package()
    output.mkdir(parents=True, exist_ok=False)
    save(output/'package.json', package)
    for arm in ('A','B'):
        save(output/f'{arm}-request.json',package['payloads'][arm])
        save(output/f'{arm}-wire-request.json',{**package['payloads'][arm],'stream':True})
        (output/f'{arm}-role-instruction.txt').write_bytes(package['roleBlocks'][arm].encode('utf-8'))
    (output/'document.txt').write_bytes(package['document'].encode('utf-8'))
    shutil.copyfile(PRIOR/'gold.json',output/'gold.json')
    save(output/'expected.json',package['expected'])
    hashes=identity()
    for path in list(output.iterdir()):
        hashes[str(path.resolve())]=digest(path)
    git=['rtk','proxy','git','-c',f'safe.directory={ROOT}', '-C',str(ROOT)]
    def state(*args):
        return subprocess.check_output(git+list(args),encoding='utf-8').strip()
    for path in identity():
        p=Path(path)
        if p.is_relative_to(ROOT):
            target=output/'code-snapshot'/p.relative_to(ROOT)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
    save(output/'freeze.json',{'revision':state('rev-parse','HEAD'),
        'workingTreeStatus':state('status','--porcelain=v1','--untracked-files=all'),
        'sha256':hashes,'endpoint':ENDPOINT,'model':MODEL,'sourceSha256':SOURCE_SHA,'goldSha256':GOLD_SHA,
        'maxCalls':2,'retries':0,'requestSeconds':600,'totalSeconds':1220,'finishReserveSeconds':20,
        'pairDiff':['messages[0].content: MENTION_ROLE_INSTRUCTION block only'],
        'expectedSentToModel':False, 'serviceModified':False,
        'freeAccessBasis':'User explicitly authorized the previously confirmed free NVIDIA endpoint for this exact two-call A/B on 2026-10-03. No independent account quota inspection; no paid fallback.',
        'python':sys.executable,'pythonVersion':sys.version,'pythonSha256':digest(Path(sys.executable))})
    check_identity(hashes)
    return package


class PairGate:
    """Only A then B; any transport, parse, contract, identity or timeout failure is terminal."""
    def __init__(self, package, output, transport, verify, *, clock=time.monotonic,
                 total_seconds=TOTAL_SECONDS, reserve=FINISH_RESERVE):
        if not 0 < reserve < total_seconds <= TOTAL_SECONDS:
            raise ValueError('INVALID_BUDGET')
        self.package,self.output,self.transport,self.verify=package,output,transport,verify
        self.clock,self.started_at=clock,clock()
        self.stop_at=self.started_at+total_seconds-reserve
        self.calls,self.stopped=[],False

    def abort(self):
        self.stopped=True

    def __call__(self,payload,key,timeout):
        if self.stopped or len(self.calls)>=2:
            raise AnalysisError('PROVIDER_FAILURE')
        try:
            self.verify()
        except BaseException:
            self.abort()
            raise
        index=len(self.calls)
        arm=('A','B')[index]
        if payload != self.package['payloads'][arm] or payload['model']!=ALLOWED_MODEL or ENDPOINT!=ALLOWED_ENDPOINT:
            self.abort()
            raise AnalysisError('PROVIDER_MODEL')
        remaining=self.stop_at-self.clock()
        limit=min(timeout,REQUEST_SECONDS,remaining-.05)
        if limit<=0:
            self.abort()
            raise AnalysisError('PROVIDER_TIMEOUT')
        row={'arm':arm,'index':index+1,'state':'started','timeoutSeconds':limit,
             'remainingWorkSeconds':remaining,'networkAttempted':False}
        self.calls.append(row)
        save(self.output/'calls.json',self.calls,replace=True)
        started=self.clock()
        try:
            # Durable recording time consumes the same remaining total budget.
            limit=min(limit,self.stop_at-self.clock()-.05)
            if limit<=0:
                raise AnalysisError('PROVIDER_TIMEOUT')
            row.update(timeoutSeconds=limit,networkAttempted=True)
            save(self.output/f'{arm}-started.json',row)
            limit=min(limit,self.stop_at-self.clock()-.05)
            if limit<=0:
                row['networkAttempted']=False
                raise AnalysisError('PROVIDER_TIMEOUT')
            row['actualTransportTimeoutSeconds']=limit
            raw=self.transport(payload,key,limit)
            _reject_sensitive(raw.decode('utf-8'),key)
            (self.output/f'{arm}-response.json').write_bytes(raw)
            if self.clock()>=self.stop_at:
                raise AnalysisError('PROVIDER_TIMEOUT')
            row['state']='received'
            return raw
        except BaseException as error:
            self.abort()
            row.update(state='failed',error=getattr(error,'code','LOCAL_FAILURE'))
            if hasattr(error,'response_diagnostic'):
                save(self.output/f'{arm}-diagnostic.json',error.response_diagnostic)
            raise
        finally:
            row['elapsedSeconds']=self.clock()-started
            save(self.output/'calls.json',self.calls,replace=True)


def quote_audit(document,candidate,raw):
    errors={'quoteAbsent':0,'occurrenceInvalid':0,'candidateNotCovered':0}
    audit=[]
    covered=False
    for group in ('support','counterEvidence'):
        for item in raw[group]:
            starts=[]
            start=-1
            while True:
                start=document.find(item['quote'],start+1)
                if start<0: break
                starts.append(start)
            valid=0<=item['occurrence']<len(starts)
            if not starts: errors['quoteAbsent']+=1
            elif not valid: errors['occurrenceInvalid']+=1
            span={'start':starts[item['occurrence']],'end':starts[item['occurrence']]+len(item['quote'])} if valid else None
            if group=='support' and span and span['start']<=candidate['start'] and span['end']>=candidate['end']:
                covered=True
            audit.append({'group':group,**item,'actualStarts':starts,'span':span})
    errors['candidateNotCovered']=int(not covered)
    return {'errors':errors,'quotes':audit}


def assess(package,reply):
    records=validate_assessments(package['document'],package['frozen'],reply['assessments'],require_mention_kind=True)
    raw_by_id={r['id']:r for r in reply['assessments']}
    rows=[]
    for expected,candidate,record in zip(package['expected'],package['frozen']['candidates'],records,strict=True):
        raw=raw_by_id[candidate['id']]
        normal=expected['field']!='other'
        rows.append({'id':candidate['id'],'candidate':candidate,'sourceValue':package['document'][candidate['start']:candidate['end']],
            'expected':expected,'raw':raw,'server':record,'citation':quote_audit(package['document'],candidate,raw),
            'normal':normal,'roleError':normal and raw['mentionKind']!=expected['mentionKind'],
            'fieldError':raw['field']!=expected['field'],
            'modelFalsePositive':raw['modelStatus']=='confirmed' and raw['field']!='other' and raw['field']!=expected['field'],
            'serverFalsePositive':record['decision']=='supported' and raw['field']!=expected['field'],
            'correctSupported':normal and record['decision']=='supported' and raw['field']==expected['field'],
            'correctExclusion':not normal and raw['field']=='other' and raw['modelStatus']=='irrelevant' and record['decision']=='excluded',
            'tentativeProposedExcluded':raw['modelStatus']=='tentative' and raw['commitment']=='proposed' and record['decision']=='excluded'})
    metrics={k:sum(bool(r[k]) for r in rows) for k in ('roleError','fieldError','modelFalsePositive','serverFalsePositive','correctSupported','correctExclusion','tentativeProposedExcluded')}
    metrics['normal7']={decision:sum(r['normal'] and r['server']['decision']==decision for r in rows)
                         for decision in ('supported','needs_confirmation','excluded')}
    metrics['normal7']['correctSupported']=sum(r['correctSupported'] for r in rows)
    metrics['uniqueNormal3']={field:any(r['correctSupported'] and r['expected']['field']==field for r in rows)
                            for field in ('project_name','project_type','external_integrations')}
    metrics['citationErrors']={k:sum(r['citation']['errors'][k] for r in rows)
                              for k in ('quoteAbsent','occurrenceInvalid','candidateNotCovered')}
    metrics['citationDefectCandidates']=sum(any(r['citation']['errors'].values()) for r in rows)
    return {'rows':rows,'metrics':metrics}


def run_pair(package,output,key,*,transport=post_nvidia_streaming,verify=lambda:None,
             clock=time.monotonic,total_seconds=TOTAL_SECONDS,reserve=FINISH_RESERVE):
    # Exclusive marker prevents restarting this pair after interruption or failure.
    save(output/'execution-start.json',{'utc':datetime.now(timezone.utc).isoformat(),
        'maxCalls':2,'retries':0,'totalSeconds':total_seconds,'finishReserveSeconds':reserve})
    gate=PairGate(package,output,transport,verify,clock=clock,total_seconds=total_seconds,reserve=reserve)
    outcomes={}
    error=None
    for arm in ('A','B'):
        diagnostic={}
        try:
            reply,model,pt,ct=NvidiaAnalyzer(key,transport=gate,model=MODEL)._send_payload(
                package['payloads'][arm],('assessments',),timeout=600,_trace=diagnostic)
            if model!=MODEL: raise AnalysisError('PROVIDER_MODEL')
            evaluated=assess(package,reply)
            if clock()>=gate.stop_at: raise AnalysisError('PROVIDER_TIMEOUT')
            verify()
            outcomes[arm]=evaluated
            save(output/f'{arm}-assessment.json',evaluated)
            gate.calls[-1]['state']='validated'
        except BaseException as exc:
            gate.abort()
            error=getattr(exc,'code','INVALID_LOCAL_OR_SEMANTIC_RESULT')
            if gate.calls:
                gate.calls[-1].update(state='failed',error=error)
            save(output/f'{arm}-failure.json',{'error':error,'exceptionType':type(exc).__name__,
                'requestSent':any(r['arm']==arm and r['networkAttempted'] for r in gate.calls)})
            break
        finally:
            # Fixed allowlist: never persist raw key, headers, or unchecked exception text.
            save(output/f'{arm}-metadata.json',{k:diagnostic.get(k) for k in (
                'model','max_tokens','prompt_tokens','completion_tokens','provider_elapsed_ms',
                'request_bytes','response_bytes','finish_reason')})
            save(output/'calls.json',gate.calls,replace=True)
    execution={'completedArms':list(outcomes),'failed':error is not None,'error':error,
        'attempts':sum(r['networkAttempted'] for r in gate.calls),'retries':0,
        'elapsedSeconds':clock()-gate.started_at,'limits':{'totalSeconds':total_seconds,'requestSeconds':600,'finishReserveSeconds':reserve},
        'unmeasuredArms':[a for a in ('A','B') if a not in outcomes]}
    save(output/'execution.json',execution)
    return execution


def live(output):
    frozen=read(output/'freeze.json')
    hashes={**frozen['sha256'],str(output/'freeze.json'):digest(output/'freeze.json')}
    check_identity(hashes)
    package=read(output/'package.json')
    verify_pair(package)
    # Current user authorization is scoped to this pair; no key/account probe requests.
    key=load_key('E:/AgentFit/.env')
    result=run_pair(package,output,key,verify=lambda:check_identity(hashes))
    check_identity(hashes)
    save(output/'integrity-after.json',{'allFrozenFilesUnchanged':True,'serviceApplied':False,'largeGoalResumed':False})
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='freeze':
        freeze(OUTPUT)
        print('FROZEN; calls=0')
    elif len(sys.argv)==2 and sys.argv[1]=='execute-approved-pair':
        live(OUTPUT)
    else:
        raise SystemExit('Use freeze or execute-approved-pair only.')
