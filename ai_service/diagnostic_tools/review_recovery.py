"""Read-only recovery inspection and synthetic review rehearsal. No live entry point.

The retained failed response stays failed. Nothing here produces a Profile.
Use in a disposable process: network_disabled temporarily patches process globals.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from functools import partial
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch

from agentfit_ai.candidate_analysis_pipeline import _merge_occurrences
from agentfit_ai.candidate_first_profile import freeze_candidate_occurrences, extract_profile_candidates
from agentfit_ai.candidate_semantic_assessment import classify_grounded_candidates
from agentfit_ai.candidate_split_review import review_candidates_separately
from agentfit_ai.operation_candidates import extract_operation_candidates
from agentfit_ai.langextract_solar_trial import extract_candidates
from .document_profile_worker import _extractions


class RecoveryRefused(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise RecoveryRefused(code)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    require(path.is_file() and not path.is_symlink(), 'MISSING_OR_UNSAFE_FILE')
    return sha(path.read_bytes())


def read(path):
    require(path.is_file() and path.stat().st_size <= 32*1024*1024, 'MISSING_OR_LARGE_RECORD')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(path.read_bytes().decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(RecoveryRefused('NONFINITE_JSON')))


def write_once(path, value):
    with path.open('xb') as handle:
        handle.write(encoded(value))
        handle.flush()
        import os
        os.fsync(handle.fileno())


@contextmanager
def network_disabled():
    """Fail even accidental DNS, provider sockets, or subprocess escape attempts."""
    with ExitStack() as stack:
        for target in ('socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.socket.sendto', 'socket.create_connection', 'socket.getaddrinfo',
                       'subprocess.Popen', 'os.system'):
            stack.enter_context(patch(target, side_effect=RecoveryRefused('NETWORK_FORBIDDEN')))
        yield


CONFIG_KEYS = ('endpoint', 'allowedModels', 'mode', 'contract', 'nvidiaOnly', 'maxCalls',
               'totalSeconds', 'perRequestSeconds', 'finishReserveSeconds', 'retries', 'firstFailureStops')
REQUIRED_RECORDS = {'freeze.json', 'source.md', 'document.txt', 'gold.json', 'trace.json',
                    'trace-checkpoint.json', 'call-metadata.json', 'request-journal.json',
                    'execution.json', 'execution-start.json', 'active-request.json', 'result.json',
                    'integrity-after.json'}


def execution_config(freeze):
    return {key: deepcopy(freeze[key]) for key in CONFIG_KEYS}


def verify_runtime(run, seal, runtime):
    files = seal['files']
    require(seal['version'] == 'recovery-origin-seal-v1' and files, 'INVALID_SEAL')
    require(REQUIRED_RECORDS <= files.keys(), 'INCOMPLETE_SEAL')
    for name, expected in files.items():
        path = run/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                path.resolve().is_relative_to(run.resolve()), 'UNSAFE_RECORD_PATH')
        require(file_hash(path) == expected, 'RECORD_HASH_MISMATCH')
    freeze = read(run/'freeze.json')
    require(all('code-snapshot/'+name in files for name in freeze['actualWorkingFileHashes']),
            'INCOMPLETE_SEAL')
    call_count=read(run/'execution.json')['requestAttempts']
    require(type(call_count) is int and 0 < call_count <= freeze['maxCalls'], 'INVALID_CALL_COUNT')
    require(all(f'deadline-{i:03}{suffix}.json' in files
                for i in range(1,call_count+1) for suffix in ('','.complete')), 'INCOMPLETE_SEAL')
    for name, expected in freeze['actualWorkingFileHashes'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                'UNSAFE_CODE_PATH')
        require(file_hash(run/'code-snapshot'/name) == expected and
                file_hash(runtime/name) == expected, 'CODE_MISMATCH')
    expected = {n for n in freeze['actualWorkingFileHashes'] if n.startswith('ai_service/agentfit_ai/')}
    actual = {p.relative_to(runtime).as_posix() for p in (runtime/'ai_service/agentfit_ai').rglob('*')
              if p.is_file() and p.suffix in ('.py', '.json', '.txt') and '__pycache__' not in p.parts}
    require(actual == expected, 'CODE_SET_MISMATCH')
    for name, module in list(sys.modules.items()):
        if name.startswith('agentfit_ai.') and getattr(module,'__file__',None):
            require(Path(module.__file__).resolve() == (runtime/'ai_service'/Path(*name.split('.'))).with_suffix('.py').resolve(),
                    'LOADED_RUNTIME_MISMATCH')
    require(file_hash(Path(sys.executable)) == freeze['pythonSha256'] and
            sys.version == freeze['pythonVersion'], 'PYTHON_MISMATCH')
    require(all(importlib.metadata.version(k) == v for k,v in freeze['packages'].items()),
            'DEPENDENCY_MISMATCH')
    return freeze


def nonnegative(value):
    return type(value) in (int,float) and math.isfinite(value) and value >= 0


def _replay(calls):
    position = 0
    def send(payload, key, timeout):
        nonlocal position
        require(position < len(calls), 'UNRECORDED_REQUEST')
        row = calls[position]
        require(payload == row['request'], 'REQUEST_CONTEXT_MISMATCH')
        require(row['error'] is None and row['response'] is not None, 'FAILED_CALL_NOT_REUSABLE')
        position += 1
        return row['response']['text'].encode('utf-8')
    return send, lambda: require(position == len(calls), 'UNCONSUMED_RECORDED_REQUEST')


def _review(document, frozen, labels, model, transport, diagnostics):
    return review_candidates_separately(document, frozen, labels, 'OFFLINE-NONCREDENTIAL',
        transport=transport, review_model=model, reasoned_review=True, adaptive_review=False,
        field_semantics='explicit-v1', review_calls=diagnostics)


class _Boundary(BaseException):
    pass


def inspect_run(run, seal, runtime, *, config=None, source=None):
    """Validate a sealed failed run; do not count transport success as review success."""
    try:
        with network_disabled():
            return _inspect(Path(run), deepcopy(seal), Path(runtime), config, source)
    except RecoveryRefused:
        raise
    except Exception as exc:
        raise RecoveryRefused('INVALID_OR_INCOMPLETE_RECORD:' + type(exc).__name__) from None


def _inspect(run, seal, runtime, config, source):
    freeze = verify_runtime(run, seal, runtime)
    require(config is None or encoded(config) == encoded(execution_config(freeze)), 'CONFIG_MISMATCH')
    require(freeze['mode'] == 'integrated-nvidia' and freeze['contract'] == 'confirmation-v3' and
            freeze['nvidiaOnly'] is True and freeze['retries'] == 0 and freeze['firstFailureStops'] is True,
            'UNSUPPORTED_EXECUTION_CONFIG')
    document = (run/'document.txt').read_bytes().decode('utf-8')
    require(sha(document.encode('utf-8')) == freeze['sourceSha256'] == file_hash(run/'source.md') and
            file_hash(Path(source) if source else Path(freeze['sourcePath'])) == freeze['sourceSha256'] and
            file_hash(run/'gold.json') == freeze['goldSha256'] == file_hash(Path(freeze['goldPath'])),
            'SOURCE_OR_GOLD_MISMATCH')
    trace, checkpoint = read(run/'trace.json'), read(run/'trace-checkpoint.json')
    require(trace['sourceSha256'] == freeze['sourceSha256'] and trace['status'] == 'partial' and
            trace['observationErrors'] == [] and checkpoint['observationErrors'] == [] and
            all(trace[k] == checkpoint[k] for k in ('documentId','sourceSha256','stages','calls')),
            'INCOMPLETE_OR_CONFLICTING_TRACE')
    stages, calls = trace['stages'], trace['calls']
    require(set(stages) == {'general_extracted','general_grounded','operations_grounded',
        'grounding_inputs','grounded','semantic_assessed','classified','call_metadata','final_response'},
        'UNSUPPORTED_STAGE_BOUNDARY')
    execution, metadata = read(run/'execution.json'), read(run/'call-metadata.json')
    journal, started = read(run/'request-journal.json'), read(run/'execution-start.json')
    result = read(run/'result.json')
    require(result == stages['final_response'] and result['outcome'] == 'failed' and
            result['contract'] == freeze['contract'] and execution['outcome'] == 'failed' and
            execution['error'] == result['error'] and metadata == stages['call_metadata'] and
            metadata['failureStage'] == 'COVERAGE_REVIEW_FAILED', 'INVALID_FAILURE_BOUNDARY')
    require(execution['requestAttempts'] == len(calls) == len(metadata['calls']) == len(journal) and
            0 < len(calls) <= freeze['maxCalls'], 'CALL_LEDGER_MISMATCH')
    require(started['mode'] == freeze['mode'] and started['nvidiaOnly'] is True and
            started['contract'] == freeze['contract'] and execution['contract'] == freeze['contract'] and
            started['maxCalls'] == freeze['maxCalls'] and started['totalSeconds'] == freeze['totalSeconds'] and
            started['finishReserveSeconds'] == freeze['finishReserveSeconds'] and started['retries'] == 0 and
            execution['retries'] == 0 and execution['limits'] == {
                'calls':freeze['maxCalls'],'totalSeconds':freeze['totalSeconds'],
                'perRequestSeconds':freeze['perRequestSeconds'],'finishReserveSeconds':freeze['finishReserveSeconds']},
            'LIMIT_RECORD_MISMATCH')
    elapsed = execution['elapsedSeconds']
    require(type(elapsed) in (int,float) and math.isfinite(elapsed) and
            0 < elapsed <= freeze['totalSeconds'], 'INVALID_CONSUMPTION')
    for i,(call,meta,row) in enumerate(zip(calls,metadata['calls'],journal),1):
        failed = i == len(calls)
        require(all(nonnegative(v) for v in (call['elapsedMs'],meta['elapsed_ms'],row['elapsedSeconds'],
                row['timeoutSeconds'],row['remainingSecondsBeforeRequest'],row['requestDeadlineMonotonic'])),
                'CONSUMPTION_MISMATCH')
        require(call['index'] == meta['call_index'] == row['index'] == i and
                call['request']['model'] == meta['requested_model'] == row['model'] and
                row['model'] in freeze['allowedModels'] and meta['provider'] == 'nvidia' and
                meta['attempt'] == 1 and meta['retry_of_call_index'] is None and
                meta['transport_completed'] is (not failed) and
                row['state'] == ('failed' if failed else 'completed') and
                bool(call['error']) == failed and bool(meta['provider_error']) == failed,
                'CALL_STATE_MISMATCH')
        require(read(run/f'deadline-{i:03}.complete.json') == row, 'INCOMPLETE_CALL_MARKER')
        initial = read(run/f'deadline-{i:03}.json')
        require(initial['state'] == 'started' and all(row[k] == v for k,v in initial.items() if k!='state') and
                0 < row['timeoutSeconds'] <= min(freeze['perRequestSeconds'],row['remainingSecondsBeforeRequest']-2) and
                0 <= row['elapsedSeconds'] <= elapsed, 'DEADLINE_MISMATCH')
        if failed:
            require(call['response'] is None and call['error'] == row['error'] == meta['provider_error'] == result['error'], 'FAILED_CALL_HAS_RESULT')
        else:
            response=call['response']
            require(response is not None and response['truncated'] is False and response['redacted'] is False and
                    len(response['text'].encode('utf-8')) == response['bytes'] == meta['response_bytes'],
                    'INCOMPLETE_RESPONSE')
    trace_times=[trace['elapsedMs'],*trace['stageElapsedMs'].values()]
    require(all(nonnegative(t) for t in trace_times), 'CONSUMPTION_MISMATCH')
    floors=[sum(c['elapsed_ms'] for c in metadata['calls'])/1000,
            sum(c['elapsedMs'] for c in calls)/1000,
            sum(r['elapsedSeconds'] for r in journal),max(trace_times)/1000]
    for row in journal:
        require(row['remainingSecondsBeforeRequest'] <= freeze['totalSeconds']-freeze['finishReserveSeconds'],
                'CONSUMPTION_MISMATCH')
        floors.append(freeze['totalSeconds']-freeze['finishReserveSeconds']-
                      row['remainingSecondsBeforeRequest']+row['elapsedSeconds'])
    require(max(floors) <= elapsed+0.05, 'CONSUMPTION_MISMATCH')
    active=read(run/'active-request.json')
    require(active['index'] == len(calls) and active['request'] == calls[-1]['request'], 'ACTIVE_REQUEST_MISMATCH')

    # Rebuild parsing, source positions and server classification using retained
    # provider bytes only. Exact payload equality is required before each replay.
    groups={}
    for call, meta in zip(calls,metadata['calls']):
        groups.setdefault(meta['stage'],[]).append(call)
    require(set(groups) == {'EXTRACTION_FAILED','OPERATION_EXTRACTION_FAILED','CLASSIFICATION_FAILED','COVERAGE_REVIEW_FAILED'},
            'UNKNOWN_STAGE_SEQUENCE')
    sequence=[m['stage'] for m in metadata['calls']]
    require(sequence == sum([[s]*len(groups[s]) for s in ('EXTRACTION_FAILED','OPERATION_EXTRACTION_FAILED','CLASSIFICATION_FAILED','COVERAGE_REVIEW_FAILED')],[]), 'STAGE_ORDER')
    sender,done=_replay(groups['EXTRACTION_FAILED'])
    extractions=extract_profile_candidates(document,'OFFLINE-NONCREDENTIAL',
        extractor=partial(extract_candidates,transport=sender,
                          nvidia_model=groups['EXTRACTION_FAILED'][0]['request']['model']))
    done()
    require(_extractions(extractions) == stages['general_extracted'] and
            freeze_candidate_occurrences(document,extractions) == stages['general_grounded'],
            'GENERAL_GROUNDING_MISMATCH')
    sender, done = _replay(groups['OPERATION_EXTRACTION_FAILED'])
    ops=extract_operation_candidates(document,'OFFLINE-NONCREDENTIAL',model=groups['OPERATION_EXTRACTION_FAILED'][0]['request']['model'],transport=sender)
    done()
    require(ops == stages['operations_grounded'] and stages['grounding_inputs'] == {
        'general':stages['general_grounded'],'operations':ops}, 'OPERATION_GROUNDING_MISMATCH')
    frozen=_merge_occurrences(document,stages['general_grounded'],ops)
    require(frozen == stages['grounded'] == stages['classified']['frozen'], 'CANDIDATE_SET_MISMATCH')
    sender,done=_replay(groups['CLASSIFICATION_FAILED'])
    assessed=classify_grounded_candidates(document,frozen,'OFFLINE-NONCREDENTIAL',
        model=groups['CLASSIFICATION_FAILED'][0]['request']['model'],transport=sender)
    done()
    require(assessed == stages['semantic_assessed'] and assessed['labels'] == stages['classified']['labels'],
            'CLASSIFICATION_MISMATCH')
    review_calls=groups['COVERAGE_REVIEW_FAILED']
    position=0
    reviewed=[]
    next_request=None
    def boundary(payload,key,timeout):
        nonlocal position,next_request
        require(position < len(review_calls), 'MISSING_REVIEW_REQUEST')
        row=review_calls[position]
        require(payload == row['request'], 'REVIEW_REQUEST_MISMATCH')
        position+=1
        if row['error'] is not None:
            next_request=deepcopy(payload)
            raise _Boundary()
        return row['response']['text'].encode('utf-8')
    try:
        _review(document,frozen,assessed['labels'],review_calls[-1]['request']['model'],boundary,reviewed)
    except _Boundary:
        pass
    require(position == len(review_calls) and next_request is not None, 'NO_FAILED_REVIEW_BOUNDARY')
    success=review_calls[:-1]
    require(len([r for r in reviewed if r['validated']]) == len(success), 'UNVALIDATED_REVIEW')
    checked=[]
    rejection_reasons=[]
    for row in success:
        data=json.loads(row['request']['messages'][1]['content'])
        checked.extend(c['id'] for c in data.get('selections',[]))
        envelope=json.loads(row['response']['text'])
        reply=json.loads(envelope['choices'][0]['message']['content'])
        rejection_reasons.extend(reply.get('rejectionReasons',[]))
    confirmed=[r['id'] for r in assessed['labels'] if r['status']=='confirmed']
    pending=[cid for cid in confirmed if cid not in checked]
    origin_id=sha(encoded({'freeze':seal['files']['freeze.json'],'documentId':trace['documentId']}))
    state={'document':document,'frozen':frozen,'labels':assessed['labels'],'reviewCalls':review_calls,
           'reviewModel':review_calls[-1]['request']['model']}
    plan={'version':'offline-review-recovery-plan-v1','originId':origin_id,'originPath':str(run.resolve()),
          'originSealSha256':sha(encoded(seal)),'originRevision':freeze['revision'],
          'stateSha256':sha(encoded(state)),'sourceSha256':freeze['sourceSha256'],
          'candidateSha256':sha(encoded(frozen)),'liveResumeAuthorized':False,
          'serviceResult':result,'analysisOutcome':'failed','candidateCount':len(frozen['candidates']),
          'reusableCompletedCallIndices':[c['index'] for c in calls[:-1]],
          'reviewedCandidateIds':checked,'pendingReviewCandidateIds':pending,
          'completedReviewRejectionReasons':rejection_reasons,
          'notSelectedForReviewCandidateIds':[r['id'] for r in assessed['labels'] if r['status']!='confirmed'],
          'nextRequest':{'originalCallIndex':calls[-1]['index'],'sha256':sha(encoded(next_request)),
                         'schemaName':next_request['response_format']['json_schema']['name']},
          'remainingReviewBatchSizes':[min(20,len(pending)-i) for i in range(0,len(pending),20)],
          'deferredStages':['source_coverage (input depends on valid review replies)',
                            'feature_curation (0–4 calls, depends on reviewed unique features)',
                            'projection (local only; not performed here)'],
          'budget':{'originalCalls':len(calls),'originalSeconds':elapsed,'callLimit':freeze['maxCalls'],
                    'totalSeconds':freeze['totalSeconds'],'perRequestSeconds':freeze['perRequestSeconds'],
                    'finishReserveSeconds':freeze['finishReserveSeconds'],
                    'remainingCalls':freeze['maxCalls']-len(calls),'remainingSeconds':freeze['totalSeconds']-elapsed},
          'missingForLiveResume':['No production resume entry or durable global claim/usage ledger.',
                'Prior first-failure/no-retry authorization ended; resend requires new explicit approval.',
                'No execution-time output signature; this seal trusts retained local records.',
                'Provider model revision/determinism and remote inference cancellation are unverified.']}
    return {'plan':plan,'planSha256':sha(encoded(plan)),
            'state':state,'run':run,'seal':seal,'runtime':runtime}


def simulate_review(audit, ledger, outcomes, *, resume_id='offline-rehearsal'):
    """Only local scripted JSON responses; no callable transport or live opt-in."""
    with network_disabled():
        verify_runtime(audit['run'],audit['seal'],audit['runtime'])
        plan,state=audit['plan'],audit['state']
        require(sha(encoded(plan)) == audit['planSha256'] and
                sha(encoded(state)) == plan['stateSha256'], 'STATE_CHANGED')
        ledger=Path(ledger)
        require(not ledger.resolve().is_relative_to(audit['run'].resolve()), 'DO_NOT_WRITE_ORIGIN')
        ledger.mkdir(parents=True,exist_ok=True)
        claim=ledger/(plan['originId']+'.claim.json')
        try:
            write_once(claim,{'originId':plan['originId'],'originSealSha256':plan['originSealSha256'],
                              'resumeId':resume_id,'kind':'synthetic-only','planSha256':sha(encoded(plan))})
        except FileExistsError:
            raise RecoveryRefused('DUPLICATE_OR_INCOMPLETE_RESUME') from None
        budget=plan['budget']
        report={'analysisOutcome':'failed','serviceResult':plan['serviceResult'],
                'originId':plan['originId'],'resumeId':resume_id,'countsAsRealQualityEvaluation':False,
                'simulationStatus':'stopped','attempts':[], 'originalCalls':budget['originalCalls'],
                'originalSeconds':budget['originalSeconds'],'syntheticCalls':0,'syntheticSeconds':0,
                'cumulativeCalls':budget['originalCalls'],'cumulativeSeconds':budget['originalSeconds'],
                'reviewedCandidateIds':list(plan['reviewedCandidateIds']),
                'pendingReviewCandidateIds':list(plan['pendingReviewCandidateIds']),
                'rejectedCandidateIds':[r['id'] for r in plan['completedReviewRejectionReasons']],'error':None}
        diagnostics=[]
        replayed=0
        pending_checked=[]
        pending_wrong=[]
        def send(payload,key,timeout):
            nonlocal replayed,pending_checked,pending_wrong
            # Reaching the next request means the previous response passed the existing validator.
            if pending_checked:
                report['attempts'][-1]['state']='validated_synthetic_review'
                report['reviewedCandidateIds'].extend(pending_checked)
                report['pendingReviewCandidateIds']=[i for i in report['pendingReviewCandidateIds'] if i not in pending_checked]
                report['rejectedCandidateIds'].extend(pending_wrong)
                pending_checked,pending_wrong=[],[]
            if replayed < len(state['reviewCalls'])-1:
                row=state['reviewCalls'][replayed]
                require(payload == row['request'], 'REPLAY_REQUEST_CHANGED')
                replayed+=1
                return row['response']['text'].encode('utf-8')
            if not report['attempts']:
                require(sha(encoded(payload)) == plan['nextRequest']['sha256'], 'RESUME_BOUNDARY_CHANGED')
            remaining=budget['totalSeconds']-report['cumulativeSeconds']-budget['finishReserveSeconds']
            require(report['cumulativeCalls'] < budget['callLimit'], 'CUMULATIVE_CALL_LIMIT')
            require(remaining > 2, 'CUMULATIVE_TIME_LIMIT')
            require(len(report['attempts']) < len(outcomes), 'SYNTHETIC_SCRIPT_EXHAUSTED')
            outcome=outcomes[len(report['attempts'])]
            duration=outcome['seconds']
            require(type(duration) in (int,float) and math.isfinite(duration) and duration>=0, 'INVALID_SYNTHETIC_TIME')
            data=json.loads(payload['messages'][1]['content'])
            ids=[r['id'] for r in data.get('selections',[])]
            limit=min(timeout,budget['perRequestSeconds'],remaining-2)
            attempt={'kind':'candidate_batch' if 'selections' in data else 'source_coverage',
                     'candidateIds':ids,'timeoutSeconds':limit,'requestSha256':sha(encoded(payload)),
                     'payload':payload,'elapsedSeconds':min(duration,limit),'state':'started'}
            report['attempts'].append(attempt)
            report['syntheticCalls']+=1
            report['cumulativeCalls']+=1
            report['syntheticSeconds']+=attempt['elapsedSeconds']
            report['cumulativeSeconds']+=attempt['elapsedSeconds']
            write_once(ledger/(plan['originId']+f'.attempt-{len(report["attempts"]):03}.json'),attempt)
            require(duration < limit, 'CUMULATIVE_TIME_LIMIT')
            require(outcome['mode'] != 'fail', 'SYNTHETIC_PROVIDER_FAILURE')
            wrong=ids[:1] if outcome['mode']=='reject_first' else []
            reply=({'checkedCandidateIds':['nonexistent'] if outcome['mode']=='invalid_ids' else ids,
                    'wrongCandidateIds':wrong,'rejectionReasons':[{'id':i,'reason':'not_product_fact'} for i in wrong]}
                   if ids else {'checkedFields':data['fields'],'missingFields':[]})
            require(outcome['mode'] in ('pass','reject_first','invalid_ids'), 'UNKNOWN_SYNTHETIC_OUTCOME')
            attempt['state']='synthetic_response_returned'
            pending_checked,pending_wrong=ids,wrong
            return encoded({'model':payload['model'],'choices':[{'index':0,'finish_reason':'stop',
                           'message':{'role':'assistant','content':json.dumps(reply)}}]})
        def recorded_send(payload,key,timeout):
            try:
                return send(payload,key,timeout)
            except RecoveryRefused as exc:
                # The existing analyzer sanitizes transport exceptions. Preserve this
                # tool's local guard code before that boundary, never raw provider text.
                report['error']=str(exc)
                raise
        try:
            _review(state['document'],state['frozen'],state['labels'],state['reviewModel'],recorded_send,diagnostics)
            report['simulationStatus']='review_complete_synthetic'
            if report['attempts']:
                report['attempts'][-1]['state']='validated_synthetic_review'
        except Exception as exc:
            report['error']=report['error'] or (str(exc) if isinstance(exc,RecoveryRefused) else 'INVALID_SYNTHETIC_REVIEW')
            if report['attempts'] and report['attempts'][-1]['state']!='validated_synthetic_review':
                report['attempts'][-1]['state']='failed_or_unvalidated'
        report['reviewDiagnostics']=diagnostics
        write_once(ledger/(plan['originId']+'.result.json'),report)
        return report


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Offline inspection only; cannot send a model request.')
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--seal',required=True,type=Path)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    with network_disabled():
        require(not args.output.resolve().is_relative_to(args.run.resolve()), 'DO_NOT_WRITE_ORIGIN')
        audit=inspect_run(args.run,read(args.seal),args.runtime)
        write_once(args.output,audit['plan'])
    print(json.dumps({'status':'offline_plan_only','liveCalls':0,'nextRequest':audit['plan']['nextRequest']}))


if __name__=='__main__':
    main()
