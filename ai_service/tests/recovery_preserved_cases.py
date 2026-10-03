"""Original recovery assertions, run only against the sealed historical code."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import zipfile

from review_preservation_fixture import offline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent/'fixtures/review_recovery'
SPEC = importlib.util.find_spec('diagnostic_tools.review_recovery')
if SPEC:
    from diagnostic_tools import review_recovery as recovery


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(SPEC, 'offline recovery inspector is not implemented')
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.run = self.folder/'origin'
        self.run.mkdir()
        self.seal = json.loads((FIXTURE/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(digest(FIXTURE/'records.zip'), self.seal['archiveSha256'])
        with zipfile.ZipFile(FIXTURE/'records.zip') as z:
            for name in self.seal['files']:
                target = self.run/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
        freeze=json.loads((self.run/'freeze.json').read_text(encoding='utf-8'))
        if sys.version != freeze['pythonVersion'] or digest(Path(sys.executable)) != freeze['pythonSha256']:
            self.skipTest('retained Windows Python binary differs; exact-runtime replay intentionally refused')
        self.guard = offline()
        self.guard.__enter__()
        self.addCleanup(self.guard.__exit__, None, None, None)
        # Every injected fault starts from a genuinely compatible runtime. A
        # prior CODE_MISMATCH must never make an unrelated negative test pass.
        recovery.verify_runtime(self.run, self.seal, ROOT)

    def audit(self, **kwargs):
        kwargs.setdefault('source',self.run/'source.md')
        return recovery.inspect_run(self.run, self.seal, ROOT, **kwargs)

    def edit(self, name, mutate, reseal=False):
        path = self.run/name
        data = json.loads(path.read_text(encoding='utf-8'))
        mutate(data)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        if reseal:
            self.seal['files'][name] = digest(path)

    def test_saved_run_plans_only_first_failed_review_and_keeps_failed_response(self):
        audit = self.audit()
        plan = audit['plan']
        self.assertEqual(plan['reusableCompletedCallIndices'], list(range(1, 24)))
        self.assertEqual(plan['nextRequest']['originalCallIndex'], 24)
        self.assertEqual(plan['candidateCount'], 156)
        self.assertEqual(len(plan['reviewedCandidateIds']), 0)
        self.assertEqual(len(plan['pendingReviewCandidateIds']), 44)
        self.assertEqual(len(plan['notSelectedForReviewCandidateIds']), 112)
        self.assertEqual(plan['remainingReviewBatchSizes'], [20, 20, 4])
        self.assertEqual(plan['budget']['originalCalls'], 24)
        self.assertAlmostEqual(plan['budget']['remainingSeconds'], 75.6643269, places=5)
        self.assertFalse(plan['liveResumeAuthorized'])
        self.assertEqual(plan['serviceResult'], {'contract': 'confirmation-v3', 'outcome': 'failed', 'error': 'PROVIDER_UNAVAILABLE'})
        self.assertNotIn('profile', plan)

    def test_corruption_and_missing_records_refused(self):
        for name in ('trace.json', 'trace-checkpoint.json', 'deadline-024.complete.json', 'execution.json'):
            path = self.run/name
            original = path.read_bytes()
            with self.subTest(name=name):
                path.unlink()
                with self.assertRaises(recovery.RecoveryRefused):
                    self.audit()
                path.write_bytes(b'{broken')
                with self.assertRaises(recovery.RecoveryRefused):
                    self.audit()
                path.write_bytes(original)

    def test_source_code_settings_and_environment_mismatches_refused(self):
        wrong = self.folder/'source.md'
        wrong.write_text('different document', encoding='utf-8')
        with self.assertRaises(recovery.RecoveryRefused):
            self.audit(source=wrong)
        freeze = json.loads((self.run/'freeze.json').read_text(encoding='utf-8'))
        config = recovery.execution_config(freeze)
        for key, value in [('contract','confirmation-v2'),('maxCalls',51),('retries',1),('allowedModels',['other']),('nvidiaOnly',False)]:
            with self.subTest(key=key), self.assertRaises(recovery.RecoveryRefused):
                self.audit(config={**config,key:value})
        with self.assertRaises(recovery.RecoveryRefused):
            recovery.verify_runtime(self.run, self.seal, self.folder/'absent-runtime')
        path = self.run/'code-snapshot/ai_service/agentfit_ai/candidate_split_review.py'
        path.write_bytes(path.read_bytes()+b'\n# changed')
        with self.assertRaises(recovery.RecoveryRefused):
            self.audit()

    def test_resealed_candidate_id_span_and_decision_corruption_still_refused(self):
        for stage, mutate in [
            ('grounded',lambda x:x['candidates'][0].update(id='C999')),
            ('classified',lambda x:x['frozen']['candidates'][0].update(start=3)),
            ('semantic_assessed',lambda x:x['modelDecisions'][0].update(decision='supported'))]:
            backup={n:(self.run/n).read_bytes() for n in ('trace.json','trace-checkpoint.json')}
            for name in backup:
                self.edit(name, lambda x:mutate(x['stages'][stage]), reseal=True)
            with self.subTest(stage=stage), self.assertRaises(recovery.RecoveryRefused):
                self.audit()
            for name,raw in backup.items():
                (self.run/name).write_bytes(raw)
                self.seal['files'][name]=digest(self.run/name)

    def test_synthetic_resume_does_not_transmit_completed_calls_or_export_profile(self):
        audit=self.audit()
        report=recovery.simulate_review(audit,self.folder/'ledger',[{'mode':'pass','seconds':1}]*4)
        self.assertEqual(report['simulationStatus'],'review_complete_synthetic')
        self.assertEqual([r['kind'] for r in report['attempts']],['candidate_batch']*3+['source_coverage'])
        self.assertEqual([len(r['candidateIds']) for r in report['attempts']], [20,20,4,0])
        self.assertEqual(report['cumulativeCalls'],28)
        self.assertEqual(len(report['reviewedCandidateIds']),44)
        self.assertEqual(report['analysisOutcome'],'failed')
        self.assertNotIn('profile',report)
        self.assertFalse(report['countsAsRealQualityEvaluation'])

    def test_first_additional_failure_stops_and_other_name_cannot_resume_again(self):
        audit=self.audit()
        ledger=self.folder/'ledger'
        report=recovery.simulate_review(audit,ledger,[{'mode':'fail','seconds':2},{'mode':'pass','seconds':1}], resume_id='one')
        self.assertEqual(report['simulationStatus'],'stopped')
        self.assertEqual(len(report['attempts']),1)
        self.assertEqual(report['cumulativeCalls'],25)
        with self.assertRaisesRegex(recovery.RecoveryRefused,'DUPLICATE_OR_INCOMPLETE_RESUME'):
            recovery.simulate_review(audit,ledger,[{'mode':'pass','seconds':1}]*4,resume_id='two')

    def test_partial_success_records_only_validated_checked_ids(self):
        report=recovery.simulate_review(self.audit(),self.folder/'ledger',[
            {'mode':'reject_first','seconds':1},{'mode':'fail','seconds':1},{'mode':'pass','seconds':1}])
        self.assertEqual(len(report['attempts']),2)
        self.assertEqual(len(report['reviewedCandidateIds']),20)
        self.assertEqual(len(report['pendingReviewCandidateIds']),24)
        self.assertEqual(report['rejectedCandidateIds'],['C006'])
        self.assertEqual(report['analysisOutcome'],'failed')

    def test_invalid_success_reply_is_not_completed_review(self):
        report=recovery.simulate_review(self.audit(),self.folder/'ledger',[
            {'mode':'invalid_ids','seconds':1},{'mode':'pass','seconds':1}])
        self.assertEqual(len(report['attempts']),1)
        self.assertEqual(report['reviewedCandidateIds'],[])
        self.assertEqual(report['simulationStatus'],'stopped')

    def test_cumulative_time_not_reset_and_timeout_has_no_followup(self):
        report=recovery.simulate_review(self.audit(),self.folder/'ledger',[
            {'mode':'pass','seconds':70},{'mode':'pass','seconds':1}])
        self.assertEqual(len(report['attempts']),1)
        self.assertEqual(report['error'],'CUMULATIVE_TIME_LIMIT')
        self.assertLess(report['attempts'][0]['timeoutSeconds'],64)
        self.assertLessEqual(report['cumulativeSeconds'],1800)

    def test_network_block_also_covers_dns_and_process_escape(self):
        with recovery.network_disabled():
            with self.assertRaises(recovery.RecoveryRefused):
                socket.getaddrinfo('example.com',443)
            with self.assertRaises(recovery.RecoveryRefused):
                subprocess.Popen(['not-a-real-program'])

    def partial_review_fixture(self):
        """Alternate synthetic retained run: one valid batch, then failed next batch."""
        rehearsal=recovery.simulate_review(self.audit(),self.folder/'setup-ledger',[
            {'mode':'reject_first','seconds':1},{'mode':'fail','seconds':1}])
        trace=json.loads((self.run/'trace.json').read_text(encoding='utf-8'))
        metadata=json.loads((self.run/'call-metadata.json').read_text(encoding='utf-8'))
        journal=json.loads((self.run/'request-journal.json').read_text(encoding='utf-8'))
        next_payload=rehearsal['attempts'][1]['payload']
        ids=rehearsal['attempts'][0]['candidateIds']
        reply={'checkedCandidateIds':ids,'wrongCandidateIds':[ids[0]],
               'rejectionReasons':[{'id':ids[0],'reason':'not_product_fact'}]}
        raw=json.dumps({'model':'z-ai/glm-5.3','choices':[{'index':0,'finish_reason':'stop',
            'message':{'role':'assistant','content':json.dumps(reply)}}]})
        old=deepcopy(trace['calls'][-1])
        trace['calls'][-1].update(error=None,response={'text':raw,'bytes':len(raw.encode()),
            'truncated':False,'redacted':False},elapsedMs=1000)
        trace['calls'].append({**old,'index':25,'request':next_payload,'elapsedMs':1000})
        failed_meta=deepcopy(metadata['calls'][-1])
        metadata['calls'][-1].update(elapsed_ms=1000,response_bytes=len(raw.encode()),
            transport_completed=True,provider_error=None)
        metadata['calls'].append({**failed_meta,'call_index':25,'elapsed_ms':1000})
        trace['stages']['call_metadata']=metadata
        failed_row=deepcopy(journal[-1])
        journal[-1].pop('error')
        journal[-1].update(state='completed',elapsedSeconds=1)
        journal.append({**failed_row,'index':25,'elapsedSeconds':1})
        def save(name,value):
            path=self.run/name
            path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
            self.seal['files'][name]=digest(path)
        for name in ('trace.json','trace-checkpoint.json'):
            save(name,trace)
        save('call-metadata.json',metadata)
        save('request-journal.json',journal)
        save('deadline-024.complete.json',journal[-2])
        save('deadline-025.complete.json',journal[-1])
        initial=json.loads((self.run/'deadline-024.json').read_text(encoding='utf-8'))
        save('deadline-025.json',{**initial,'index':25})
        self.edit('execution.json',lambda x:x.update(requestAttempts=25),reseal=True)
        save('active-request.json',{'index':25,'state':'started','request':next_payload})

    def test_stored_partial_review_reuses_success_and_resumes_second_batch(self):
        self.partial_review_fixture()
        audit=self.audit()
        plan=audit['plan']
        self.assertEqual(plan['nextRequest']['originalCallIndex'],25)
        self.assertEqual(len(plan['reviewedCandidateIds']),20)
        self.assertEqual(plan['remainingReviewBatchSizes'],[20,4])
        report=recovery.simulate_review(audit,self.folder/'partial-ledger',[{'mode':'pass','seconds':1}]*3)
        self.assertEqual(len(report['attempts']),3)
        self.assertNotIn('C006',report['attempts'][0]['candidateIds'])
        self.assertEqual(report['rejectedCandidateIds'],['C006'])
        self.assertEqual(len(report['reviewedCandidateIds']),44)

    def test_mutated_plan_cannot_reset_budget_and_exhausted_limit_stops_before_send(self):
        audit=self.audit()
        audit['plan']['budget']['originalCalls']=0
        with self.assertRaisesRegex(recovery.RecoveryRefused,'STATE_CHANGED'):
            recovery.simulate_review(audit,self.folder/'tampered',[])
        # Alternate frozen authorization with its complete call allowance already consumed.
        self.edit('freeze.json',lambda x:x.update(maxCalls=24),reseal=True)
        self.edit('execution-start.json',lambda x:x.update(maxCalls=24),reseal=True)
        self.edit('execution.json',lambda x:x['limits'].update(calls=24),reseal=True)
        report=recovery.simulate_review(self.audit(),self.folder/'capped',[{'mode':'pass','seconds':1}])
        self.assertEqual(report['error'],'CUMULATIVE_CALL_LIMIT')
        self.assertEqual(report['attempts'],[])
        self.assertEqual(report['cumulativeCalls'],24)

    def test_invalid_saved_review_cannot_be_reused_even_when_transport_succeeded(self):
        self.partial_review_fixture()
        for name in ('trace.json','trace-checkpoint.json'):
            def corrupt(data):
                row=data['calls'][-2]
                parsed=json.loads(row['response']['text'])
                reply=json.loads(parsed['choices'][0]['message']['content'])
                reply['checkedCandidateIds'][0]='C999'
                parsed['choices'][0]['message']['content']=json.dumps(reply)
                row['response']['text']=json.dumps(parsed)
            self.edit(name,corrupt,reseal=True)
        with self.assertRaises(recovery.RecoveryRefused):
            self.audit()

    def test_seal_cannot_omit_required_trace_even_if_file_still_exists(self):
        self.seal['files'].pop('trace.json')
        with self.assertRaisesRegex(recovery.RecoveryRefused,'INCOMPLETE_SEAL'):
            self.audit()

    def test_runtime_hash_check_must_be_bound_to_loaded_analysis_code(self):
        with self.assertRaisesRegex(recovery.RecoveryRefused,'LOADED_RUNTIME_MISMATCH'):
            recovery.verify_runtime(self.run,self.seal,self.run/'code-snapshot')

    def test_elapsed_cannot_be_reduced_below_retained_deadline_consumption(self):
        self.edit('execution.json',lambda x:x.update(elapsedSeconds=x['elapsedSeconds']-1),reseal=True)
        with self.assertRaisesRegex(recovery.RecoveryRefused,'CONSUMPTION_MISMATCH'):
            self.audit()

    def test_general_extraction_prompt_and_raw_response_must_match_saved_stage(self):
        for name in ('trace.json','trace-checkpoint.json'):
            self.edit(name,lambda x:x['calls'][0]['request']['messages'][0].update(content='Different prompt'),reseal=True)
        with self.assertRaises(recovery.RecoveryRefused):
            self.audit()

    def test_corrupt_general_extraction_response_refused_after_resealing(self):
        for name in ('trace.json','trace-checkpoint.json'):
            def corrupt(x):
                x['calls'][0]['response'].update(text='{broken',bytes=7)
                x['stages']['call_metadata']['calls'][0]['response_bytes']=7
            self.edit(name,corrupt,reseal=True)
        self.edit('call-metadata.json',lambda x:x['calls'][0].update(response_bytes=7),reseal=True)
        with self.assertRaises(recovery.RecoveryRefused):
            self.audit()

    def test_unexpected_stage_cannot_be_silently_ignored(self):
        for name in ('trace.json','trace-checkpoint.json'):
            self.edit(name,lambda x:x['stages'].update(unexpected_extra_stage={}),reseal=True)
        with self.assertRaises(recovery.RecoveryRefused):
            self.audit()

    def test_negative_recorded_cost_cannot_credit_the_original_budget(self):
        for name in ('trace.json','trace-checkpoint.json'):
            self.edit(name,lambda x:x['stages']['call_metadata']['calls'][0].update(elapsed_ms=-2000000),reseal=True)
        self.edit('call-metadata.json',lambda x:x['calls'][0].update(elapsed_ms=-2000000),reseal=True)
        self.edit('execution.json',lambda x:x.update(elapsedSeconds=400),reseal=True)
        with self.assertRaisesRegex(recovery.RecoveryRefused,'CONSUMPTION_MISMATCH'):
            self.audit()

    def test_historical_service_prompt_schema_and_a_block_exactly_match(self):
        from agentfit_ai.candidate_semantic_assessment import assessment_payload
        from agentfit_ai.candidate_mention_roles import MENTION_ROLE_INSTRUCTION
        from tentative_proposed_fixture import load
        for doc, item in load('suite.json')['documents'].items():
            generated = assessment_payload(item['document'], item['frozen']['candidates'])
            self.assertEqual(generated['messages'], item['payloads']['A']['messages'])
            self.assertEqual(generated['response_format'], item['payloads']['A']['response_format'])
            self.assertEqual(MENTION_ROLE_INSTRUCTION, load(f'{doc}/A-role-instruction.txt'))
            self.assertNotEqual(MENTION_ROLE_INSTRUCTION, load(f'{doc}/B-role-instruction.txt'))

    def test_historical_v2_v3_all_classification_requests_match_a_builder(self):
        from agentfit_ai.candidate_semantic_assessment import assessment_payload
        from test_mention_role_cause import recorded_batches
        for version in ('v2', 'v3'):
            batches = recorded_batches(version)
            self.assertTrue(batches)
            for batch in batches:
                with self.subTest(version=version, call=batch['call']['index']):
                    generated = assessment_payload(batch['document'], batch['frozen']['candidates'])
                    self.assertEqual(batch['call']['request']['messages'], generated['messages'])
                    self.assertEqual(batch['call']['request']['response_format'], generated['response_format'])
                    self.assertEqual(batch['input']['document'], batch['document'])

    def test_historical_a_transport_replay_preserves_exact_v2_and_v3_review(self):
        from review_preservation_fixture import load, replay
        v2 = replay(historical_classification=True)
        self.assertEqual(v2, load('result.json'))
        v3 = replay('confirmation-v3', historical_classification=True)
        for key in ('profile', 'modelDecisions', 'questions', 'unassignedQuestions', 'fieldStates'):
            self.assertEqual(v3[key], v2[key], key)
        self.assertEqual(len(v3['reviewDispositions']), 6)
        self.assertTrue(all(r['disposition'] == 'needs_confirmation' for r in v3['reviewDispositions']))

    def test_historical_observer_records_all_22_a_replay_requests(self):
        from test_document_profile_v3_observer import observed_replay, DocumentProfileV3ObserverTests
        from diagnostic_tools.document_profile_worker import execute_observed_request
        from review_preservation_fixture import load
        with observed_replay(historical_classification=True):
            target = self.folder/'historical-trace.json'
            request = DocumentProfileV3ObserverTests().request('confirmation-v3')
            result = json.loads(execute_observed_request(request, target))
            trace = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(result['contract'], 'confirmation-v3')
            self.assertEqual(len(result['reviewDispositions']), 6)
            self.assertEqual(trace['stages']['final_response'], result)
            self.assertEqual(trace['observationErrors'], [])
            self.assertEqual(trace['status'], 'complete')
            self.assertEqual(len(trace['calls']), 22)
            self.assertEqual([c['request'] for c in trace['calls']],
                             [c['request'] for c in load('trace.json')['calls'][3:]])


if __name__=='__main__':
    unittest.main()
