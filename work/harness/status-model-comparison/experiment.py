"""Model-only offline comparison; no per-model payload tuning or service imports of this harness."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT/'specs/ai-developer/status-model-comparison'
_spec = importlib.util.spec_from_file_location('model_status_baseline',
    ROOT/'work/harness/status-definition-unification/experiment.py')
status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(status)
compare = status.compare
AnalysisError, write_json = compare.AnalysisError, compare.write_json
from agentfit_ai.solar import SolarAnalyzer
from agentfit_ai.deepseek_evaluation import ENDPOINT

MODELS = {'D':'deepseek-ai/deepseek-v4.1-flash','G':'z-ai/glm-5.3'}
ARMS = tuple(MODELS)
SCHEDULE = (('FR','G',1),('FR','D',1),('FR','D',2),('FR','G',2),
            ('LS','D',1),('LS','G',1),('LS','G',2),('LS','D',2))


def build_model_pair(saved_package: dict) -> dict:
    documents = {}
    if set(saved_package['documents']) != {'FR','LS'}:
        raise ValueError('INVALID_DOCUMENTS')
    for doc_id,source in saved_package['documents'].items():
        original = source['pair']['payloads']['US']
        if len(original)!=2 or len(source['frozen']['candidates'])!=16 or len(source['gold'])!=16:
            raise ValueError('INVALID_PACKAGE')
        documents[doc_id] = {k:deepcopy(source[k]) for k in ('document','frozen','gold')}
        payloads = {}
        for arm,model in MODELS.items():
            payloads[arm] = deepcopy(original)
            for payload in payloads[arm]:
                if payload['model'] != MODELS['D']:
                    raise ValueError('INVALID_BASE_MODEL')
                payload['model'] = model
        documents[doc_id]['pair']={'registry':deepcopy(source['pair']['registry']),'payloads':payloads}
    jobs = [{'docId':doc,'arm':arm,'batch':batch,
             'payload':documents[doc]['pair']['payloads'][arm][batch-1]} for doc,arm,batch in SCHEDULE]
    return {'documents':documents,'jobs':jobs,'arm_labels':dict(MODELS)}


def check_free(path, *, now=None):
    """A new, run-scoped human confirmation. Old records are never accepted."""
    try:
        record=json.loads(Path(path).read_bytes().decode('utf-8'))
        now=now or datetime.now(timezone.utc)
        confirmed=datetime.fromisoformat(record['confirmed_at'])
        expiry=datetime.fromisoformat(record['expires_at'])
        remaining=(expiry-now).total_seconds()
        valid=(record['version']=='status-model-free-v1' and record['confirmed_by']=='user'
               and record['confirmed_no_additional_charge'] is True and record['no_paid_fallback'] is True
               and record['endpoint']==ENDPOINT and sorted(record['models'])==sorted(MODELS.values())
               and type(record['max_calls']) is int and record['max_calls']==8
               and type(record['retries']) is int and record['retries']==0
               and confirmed.tzinfo is not None and expiry.tzinfo is not None
               and confirmed<=now<expiry and 0<(expiry-confirmed).total_seconds()<=5400)
    except (OSError,ValueError,TypeError,KeyError):
        valid=False
    if not valid:
        raise ValueError('FREE_ACCESS_UNCONFIRMED')
    return remaining


class FixedPayloadSender:
    """Use the unchanged response parser without NvidiaAnalyzer's model-specific conversion."""
    def __init__(self,key,transport):
        self.key,self.transport=key,transport

    def _send_payload(self,payload,names,*,_trace=None,timeout=600):
        expected=payload['model']
        if expected not in MODELS.values():
            raise ValueError('INVALID_BASE_MODEL')
        def checked_transport(_parser_payload,key,limit):
            raw=self.transport(payload,key,limit)
            try:
                reported=json.loads(raw).get('model')
            except (ValueError,TypeError,AttributeError):
                reported=None
            if reported!=expected:
                raise AnalysisError('PROVIDER_MODEL')
            return raw
        # This extra field is required only by the existing parser's local trace.
        # The closure above always transmits the original frozen payload.
        parser=SolarAnalyzer(self.key,transport=checked_transport)
        trace=_trace if _trace is not None else {}
        reply,_,pt,ct=parser._send_payload(dict(payload,reasoning_effort='none'),names,
                                          _trace=trace,timeout=timeout)
        trace.update(model=expected,request_bytes=len(json.dumps(payload).encode('utf-8')))
        trace.pop('reasoning_effort',None)
        return reply,expected,pt,ct


class ModelCallGate:
    """One exact eight-attempt schedule, terminal failure, no retry and no paid fallback."""
    def __init__(self,output,jobs,*,check_free,check_identity,transport,clock=time.monotonic):
        if ([(j['docId'],j['arm'],j['batch']) for j in jobs]!=list(SCHEDULE)
                or any(j['payload']['model']!=MODELS[j['arm']] for j in jobs)):
            raise ValueError('INVALID_JOB_COUNT')
        self.output=Path(output)
        self.output.mkdir(parents=True,exist_ok=True)
        if list(self.output.iterdir()):
            raise ValueError('CALL_DIRECTORY_NOT_EMPTY')
        self.jobs=deepcopy(jobs)
        self.check_free,self.check_identity,self.transport=check_free,check_identity,transport
        self.clock,self.start=clock,clock()
        self.started,self.stopped,self.stop_reason=0,False,None
        self.completed=[]

    def __call__(self,payload,key,timeout):
        if self.stopped or self.started>=8:
            raise ValueError('CALLS_STOPPED')
        try:
            remaining=self.check_free()
            self.check_identity()
            job=self.jobs[self.started]
            if json.dumps(payload)!=json.dumps(job['payload']):
                raise ValueError('PAYLOAD_ORDER_CHANGED')
            if type(timeout) not in (int,float) or not math.isfinite(timeout):
                raise ValueError('DEADLINE_EXPIRED')
            limit=min(timeout,600,remaining,5400-(self.clock()-self.start))
            if limit<=0:
                raise ValueError('DEADLINE_EXPIRED')
            sequence=self.started+1
            prefix=self.output/f'{sequence:02d}'
            label={k:job[k] for k in ('docId','arm','batch')}
            write_json(str(prefix)+'-request.json',payload)
            write_json(str(prefix)+'-wire-request.json',{**payload,'stream':True})
            write_json(str(prefix)+'-started.json',dict(label,sequence=sequence,model=payload['model'],
                       utc=datetime.now(timezone.utc).isoformat(),timeout_seconds=limit))
            self.started+=1
            start=self.clock()
            metadata=dict(label,sequence=sequence,model=payload['model'],returned=False,error='INTERRUPTED')
            try:
                raw=self.transport(payload,key,limit)
                with Path(str(prefix)+'-response.json').open('xb') as handle:
                    handle.write(raw)
                metadata.update(returned=True,error=None)
                return raw
            except Exception as exc:
                metadata['error']=compare.safe_error(exc)
                raise
            finally:
                metadata['seconds']=self.clock()-start
                write_json(str(prefix)+'-finished.json',metadata)
                self.completed.append(metadata)
        except Exception as exc:
            self.stopped,self.stop_reason=True,compare.safe_error(exc)
            raise
