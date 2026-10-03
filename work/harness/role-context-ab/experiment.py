"""Independent synthetic-context evaluation. Service constants remain unchanged."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('previous_role_ab', HERE.parent/'mention-role-guidance-ab/experiment.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
PREVIOUS = Path('E:/AgentFit/output/mention-role-guidance-ab-20261003-v2')
OUTPUT = Path('E:/AgentFit/output/role-context-ab-20261003-v1')
SCHEDULE = [['D1','A'], ['D1','B'], ['D2','B'], ['D2','A']]
read, save, digest = base.read, base.save, base.digest


def build_suite():
    old = read(PREVIOUS/'freeze.json')
    for name in ('A-role-instruction.txt', 'B-role-instruction.txt', 'A-request.json'):
        path = PREVIOUS/name
        if digest(path) != old['sha256'][str(path.resolve())]:
            raise ValueError('PRIOR_FREEZE_CHANGED')
    blocks = {arm:(PREVIOUS/f'{arm}-role-instruction.txt').read_bytes().decode('utf-8') for arm in ('A','B')}
    if blocks['A'] != base.MENTION_ROLE_INSTRUCTION:
        raise ValueError('SERVICE_ROLE_INSTRUCTION_CHANGED')
    suite = {'schedule': deepcopy(SCHEDULE), 'documents': {}}
    for item in read(HERE/'cases.json')['documents']:
        document = '\n'.join(item['lines'])+'\n'
        candidates, expected = [], []
        for i, case in enumerate(item['cases']):
            line = item['lines'][case['line']]
            if line.count(case['value']) != 1:
                raise ValueError('CASE_OCCURRENCE_AMBIGUOUS')
            start = sum(len(s)+1 for s in item['lines'][:case['line']])+line.index(case['value'])
            candidate = {'id': f'C{i:03}', 'start':start, 'end':start+len(case['value'])}
            candidates.append(candidate)
            expected.append({**deepcopy(case), 'id':candidate['id'], 'source':line})
            if 'counterLine' in case:
                n = case['counterLine']
                text = item['lines'][n]
                offset = sum(len(s)+1 for s in item['lines'][:n])
                expected[-1]['requiredCounterSpan'] = {'start':offset+text.index(case['value']), 'end':offset+len(text)}
                expected[-1]['counterSource'] = text
        if len(candidates)!=8 or candidates != sorted(candidates, key=lambda c:c['start']):
            raise ValueError('CASE_COUNT_OR_ORDER')
        frozen = {'candidates':candidates, 'rejected':[]}
        from agentfit_ai.operation_candidates import _validate_frozen
        _validate_frozen(document, frozen)
        a = base.nvidia_payload(base.assessment_payload(document, candidates), model=base.MODEL)
        previous = read(PREVIOUS/'A-request.json')
        if a['messages'][0] != previous['messages'][0]:
            raise ValueError('OTHER_INSTRUCTIONS_CHANGED')
        options = lambda p:{k:v for k,v in p.items() if k not in ('messages','response_format')}
        if options(a) != options(previous):
            raise ValueError('OPTIONS_CHANGED')
        b = deepcopy(a)
        b['messages'][0]['content'] = b['messages'][0]['content'].replace(blocks['A'],blocks['B'])
        package = {'document':document, 'frozen':frozen, 'expected':expected,
                   'payloads':{'A':a,'B':b}, 'roleBlocks':blocks}
        base.verify_pair(package)
        suite['documents'][item['id']] = package
    verify_suite(suite)
    return suite


def verify_suite(suite):
    if suite['schedule']!=SCHEDULE or set(suite['documents'])!={'D1','D2'}:
        raise ValueError('SCHEDULE_CHANGED')
    for p in suite['documents'].values():
        base.verify_pair(p)
        if len(p['frozen']['candidates'])!=8 or len(p['expected'])!=8:
            raise ValueError('CANDIDATE_COUNT_CHANGED')
        for c,e in zip(p['frozen']['candidates'],p['expected'],strict=True):
            if c['id']!=e['id'] or p['document'][c['start']:c['end']]!=e['value']:
                raise ValueError('SOURCE_SPAN_CHANGED')


def assess(package, reply):
    records=base.validate_assessments(package['document'],package['frozen'],reply['assessments'],require_mention_kind=True)
    raw_by_id={r['id']:r for r in reply['assessments']}
    rows=[]
    for c,e,s in zip(package['frozen']['candidates'],package['expected'],records,strict=True):
        r=raw_by_id[c['id']]
        axes={axis:r[axis] in allowed for axis,allowed in e['axes'].items()}
        counter=e.get('requiredCounterSpan')
        support_ok=s['groundingValid'] and any(q['start']<=c['start'] and q['end']>=c['end'] for q in s['support'])
        conflict_ok=counter is None or (support_ok and any(q['start']<=counter['start'] and q['end']>=counter['end'] for q in s['counterEvidence']))
        field_ok=r['field'] in e['fields']
        raw_ok=field_ok and r['mentionKind']==e['mentionKind'] and r['modelStatus']==e['modelStatus'] and all(axes.values()) and conflict_ok
        positive=e['category']=='positive'
        rows.append({'id':c['id'],'candidate':c,'sourceValue':e['value'],'expected':e,'raw':r,'server':s,
            'citation':base.quote_audit(package['document'],c,r),'axesMatch':axes,'conflictEvidenceSelected':conflict_ok if counter else None,
            'rawCorrect':raw_ok,'roleError':r['mentionKind']!=e['mentionKind'],'fieldError':not field_ok,
            'statusError':r['modelStatus']!=e['modelStatus'],'otherConfirmed':r['field']=='other' and r['modelStatus']=='confirmed',
            'modelFalsePositive':r['modelStatus']=='confirmed' and r['field']!='other' and (not positive or not field_ok or not all(axes.values())),
            'serverFalsePositive':s['decision']=='supported' and (not positive or not field_ok or not all(axes.values())),
            'correctSupported':positive and raw_ok and s['decision']=='supported',
            'correctExclusion':e['category']=='out_of_scope' and raw_ok and s['decision']=='excluded',
            'correctNegative':e['category']=='negative' and raw_ok and s['decision']=='excluded',
            'correctUncertainty':e['category'] in ('undecided','conflict') and raw_ok,
            'correctHold':e['category'] in ('undecided','conflict') and raw_ok and s['decision']=='needs_confirmation',
            'tentativeProposedExcluded':r['modelStatus']=='tentative' and r['commitment']=='proposed' and s['decision']=='excluded'})
    keys=('rawCorrect','roleError','fieldError','statusError','otherConfirmed','modelFalsePositive','serverFalsePositive',
          'correctSupported','correctExclusion','correctNegative','correctUncertainty','correctHold','tentativeProposedExcluded')
    metrics={k:sum(bool(r[k]) for r in rows) for k in keys}
    metrics['normal']={d:sum(r['expected']['category']=='positive' and r['server']['decision']==d for r in rows)
                       for d in ('supported','needs_confirmation','excluded')}
    metrics['normal']['count']=sum(r['expected']['category']=='positive' for r in rows)
    metrics['citationErrors']={k:sum(r['citation']['errors'][k] for r in rows) for k in ('quoteAbsent','occurrenceInvalid','candidateNotCovered')}
    metrics['citationDefectCandidates']=sum(any(r['citation']['errors'].values()) for r in rows)
    metrics['decisions']={d:sum(r['server']['decision']==d for r in rows) for d in ('supported','needs_confirmation','excluded')}
    return {'rows':rows,'metrics':metrics}


def identity():
    hashes=base.identity()
    paths=list(HERE.glob('*.py'))+[HERE/'cases.json', ROOT/'specs/ai-developer/mention-role-cause-analysis/context-comparison-plan.md', PREVIOUS/'freeze.json', PREVIOUS/'A-request.json',
                                 PREVIOUS/'A-role-instruction.txt', PREVIOUS/'B-role-instruction.txt']
    hashes.update({str(p.resolve()):digest(p) for p in paths})
    return hashes


def freeze(output):
    suite=build_suite()
    output.mkdir(parents=True,exist_ok=False)
    save(output/'suite.json',suite)
    save(output/'schedule.json',suite['schedule'])
    for doc,p in suite['documents'].items():
        sub=output/doc
        sub.mkdir()
        (sub/'document.txt').write_bytes(p['document'].encode('utf-8'))
        save(sub/'candidates.json',p['frozen'])
        save(sub/'expected.json',p['expected'])
        for arm in ('A','B'):
            save(sub/f'{arm}-request.json',p['payloads'][arm])
            save(sub/f'{arm}-wire-request.json',{**p['payloads'][arm],'stream':True})
            (sub/f'{arm}-role-instruction.txt').write_bytes(p['roleBlocks'][arm].encode('utf-8'))
    hashes=identity()
    for name in list(hashes):
        p=Path(name)
        if p.is_relative_to(ROOT):
            dest=output/'code-snapshot'/p.relative_to(ROOT)
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,dest)
    hashes.update({str(p.resolve()):digest(p) for p in output.rglob('*') if p.is_file()})
    git=['rtk','proxy','git','-C',str(ROOT)]
    def state(*args): return subprocess.check_output(git+list(args),encoding='utf-8').strip()
    save(output/'freeze.json',{'utc':datetime.now(timezone.utc).isoformat(),'revision':state('rev-parse','HEAD'),
        'workingTreeStatus':state('status','--porcelain=v1','--untracked-files=all'),'sha256':hashes,
        'model':base.MODEL,'endpoint':base.ENDPOINT,'maxCalls':4,'retries':0,'totalSeconds':1220,'requestSeconds':600,'finishReserveSeconds':20,
        'schedule':SCHEDULE,'expectedSentToModel':False,'pairDiff':'MENTION_ROLE_INSTRUCTION only within each document',
        'BSource':str(PREVIOUS/'B-role-instruction.txt'),'synthetic':True,'agentfitGoldChanged':False,
        'freeAccessBasis':'Current user explicitly permits the previously confirmed free NVIDIA endpoint and existing DeepSeek for this exact max-four-call comparison. No quota probe, paid conversion or fallback.',
        'python':sys.executable,'pythonVersion':sys.version,'pythonFlags':str(sys.flags),'pythonSha256':digest(Path(sys.executable))})
    base.check_identity(hashes)
    return suite


class Gate:
    """Single shared budget and terminal failure latch over all four transmissions."""
    def __init__(self,suite,output,transport,verify,*,clock=time.monotonic,total_seconds=1220,reserve=20):
        if not 0<reserve<total_seconds<=1220:
            raise ValueError('INVALID_BUDGET')
        verify_suite(suite)
        self.suite,self.output,self.transport,self.verify=suite,output,transport,verify
        self.clock,self.started_at=clock,clock()
        self.stop_at=self.started_at+total_seconds-reserve
        self.calls,self.stopped=[],False

    def abort(self): self.stopped=True

    def __call__(self,payload,key,timeout):
        if self.stopped or len(self.calls)>=4:
            raise base.AnalysisError('PROVIDER_FAILURE')
        try: self.verify()
        except BaseException:
            self.abort()
            raise
        doc,arm=self.suite['schedule'][len(self.calls)]
        if payload!=self.suite['documents'][doc]['payloads'][arm] or payload['model']!=base.ALLOWED_MODEL or base.ENDPOINT!=base.ALLOWED_ENDPOINT:
            self.abort()
            raise base.AnalysisError('PROVIDER_MODEL')
        remaining=self.stop_at-self.clock()
        limit=min(timeout,600,remaining-.05)
        if limit<=0:
            self.abort()
            raise base.AnalysisError('PROVIDER_TIMEOUT')
        row={'document':doc,'arm':arm,'index':len(self.calls)+1,'state':'started','timeoutSeconds':limit,
             'remainingWorkSeconds':remaining,'networkAttempted':False}
        self.calls.append(row)
        save(self.output/'calls.json',self.calls,replace=True)
        started=self.clock()
        sub=self.output/doc
        try:
            limit=min(limit,self.stop_at-self.clock()-.05)
            if limit<=0: raise base.AnalysisError('PROVIDER_TIMEOUT')
            save(sub/f'{arm}-started.json',row)
            limit=min(limit,self.stop_at-self.clock()-.05)
            if limit<=0: raise base.AnalysisError('PROVIDER_TIMEOUT')
            row.update(actualTransportTimeoutSeconds=limit,networkAttempted=True)
            save(self.output/'calls.json',self.calls,replace=True)
            limit=min(limit,self.stop_at-self.clock()-.05)
            if limit<=0:
                row['networkAttempted']=False
                raise base.AnalysisError('PROVIDER_TIMEOUT')
            row['actualTransportTimeoutSeconds']=limit
            raw=self.transport(payload,key,limit)
            base._reject_sensitive(raw.decode('utf-8'),key)
            base.NvidiaAnalyzer(key,transport=lambda *_:raw,model=base.MODEL)._send_payload(payload,('assessments',),timeout=limit)
            with (sub/f'{arm}-response.json').open('xb') as f: f.write(raw)
            if self.clock()>=self.stop_at: raise base.AnalysisError('PROVIDER_TIMEOUT')
            row['state']='received'
            return raw
        except BaseException as error:
            self.abort()
            row.update(state='failed',error=getattr(error,'code','LOCAL_FAILURE'))
            if hasattr(error,'response_diagnostic'): save(sub/f'{arm}-diagnostic.json',error.response_diagnostic)
            raise
        finally:
            row['elapsedSeconds']=self.clock()-started
            save(self.output/'calls.json',self.calls,replace=True)


def run_all(suite,output,key,*,transport=base.post_nvidia_streaming,verify=lambda:None,
            clock=time.monotonic,total_seconds=1220,reserve=20):
    gate=Gate(suite,output,transport,verify,clock=clock,total_seconds=total_seconds,reserve=reserve)
    save(output/'execution-start.json',{'utc':datetime.now(timezone.utc).isoformat(),'maxCalls':4,'retries':0,
                                      'totalSeconds':total_seconds,'finishReserveSeconds':reserve,'schedule':SCHEDULE})
    completed=[]
    error=None
    for doc,arm in SCHEDULE:
        sub=output/doc
        sub.mkdir(exist_ok=True)
        diagnostic={}
        try:
            p=suite['documents'][doc]
            reply,model,_,_=base.NvidiaAnalyzer(key,transport=gate,model=base.MODEL)._send_payload(
                p['payloads'][arm],('assessments',),timeout=600,_trace=diagnostic)
            if model!=base.MODEL: raise base.AnalysisError('PROVIDER_MODEL')
            evaluation=assess(p,reply)
            if clock()>=gate.stop_at: raise base.AnalysisError('PROVIDER_TIMEOUT')
            verify()
            save(sub/f'{arm}-assessment.json',evaluation)
            completed.append([doc,arm])
            gate.calls[-1]['state']='validated'
        except BaseException as exc:
            gate.abort()
            error=getattr(exc,'code','INVALID_LOCAL_OR_SEMANTIC_RESULT')
            current=next((r for r in gate.calls if r['document']==doc and r['arm']==arm),None)
            if current: current.update(state='failed',error=error)
            save(sub/f'{arm}-failure.json',{'error':error,'exceptionType':type(exc).__name__,
                                          'requestSent':bool(current and current['networkAttempted'])})
            break
        finally:
            save(sub/f'{arm}-metadata.json',{k:diagnostic.get(k) for k in ('model','max_tokens','prompt_tokens',
                'completion_tokens','provider_elapsed_ms','request_bytes','response_bytes','finish_reason')})
            save(output/'calls.json',gate.calls,replace=True)
    result={'completed':completed,'failed':error is not None,'error':error,
        'attempts':sum(r['networkAttempted'] for r in gate.calls),'retries':0,'elapsedSeconds':clock()-gate.started_at,
        'limits':{'totalSeconds':total_seconds,'requestSeconds':600,'finishReserveSeconds':reserve},
        'completePairs':[doc for doc in ('D1','D2') if all([doc,a] in completed for a in ('A','B'))],
        'unmeasured':[step for step in SCHEDULE if step not in completed]}
    save(output/'execution.json',result)
    return result


def live(output):
    manifest=read(output/'freeze.json')
    hashes={**manifest['sha256'],str((output/'freeze.json').resolve()):digest(output/'freeze.json')}
    base.check_identity(hashes)
    suite=read(output/'suite.json')
    verify_suite(suite)
    key=base.load_key('E:/AgentFit/.env')
    result=run_all(suite,output,key,verify=lambda:base.check_identity(hashes))
    base.check_identity(hashes)
    save(output/'integrity-after.json',{'allFrozenFilesUnchanged':True,'serviceApplied':False,'largeGoalResumed':False})
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['freeze']:
        freeze(OUTPUT)
        print('FROZEN; calls=0')
    elif sys.argv[1:]==['execute-approved-comparison']:
        live(OUTPUT)
    else: raise SystemExit('Use freeze or execute-approved-comparison only.')
