from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import experiment as ex
sys.path.insert(0,str(ex.ROOT/'ai_service/tests'))
from review_preservation_fixture import offline


def reply(p):
    rows=[]
    for e in p['expected']:
        row={'id':e['id'],'field':e['fields'][0],'mentionKind':e['mentionKind'], 'modelStatus':e['modelStatus'],
             'scope':'target','time':'current','polarity':'positive','commitment':'adopted','role':'product_fact',
             'conflictsChecked':True,'support':[{'quote':e['source'],'occurrence':0}], 'counterEvidence':[]}
        row.update({a:allowed[0] for a,allowed in e['axes'].items()})
        if 'counterSource' in e: row['counterEvidence']=[{'quote':e['counterSource'],'occurrence':0}]
        rows.append(row)
    return {'assessments':rows}


def envelope(p):
    return json.dumps({'model':ex.base.MODEL,'choices':[{'finish_reason':'stop','message':{
        'content':json.dumps(reply(p),ensure_ascii=False)}}]},ensure_ascii=False).encode()

class ContextPreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.suite=ex.build_suite()

    def setUp(self):
        root=ex.ROOT/'tmp'
        root.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=root,prefix='role-context-test-')
        self.output=Path(self.tmp.name)
        self.assertTrue(self.output.resolve().is_relative_to(root.resolve()))
        self.addCleanup(self.tmp.cleanup)
        guard=offline()
        guard.__enter__()
        self.addCleanup(guard.__exit__,None,None,None)

    def transport(self,payload,key,timeout):
        document=json.loads(payload['messages'][1]['content'])['document']
        p=next(p for p in self.suite['documents'].values() if p['document']==document)
        self.assertLessEqual(timeout,600)
        return envelope(p)

    def test_two_documents_eight_each_and_counterbalanced_schedule(self):
        suite = self.suite
        self.assertIsInstance(suite, dict)
        self.assertEqual(suite['schedule'], [['D1','A'],['D1','B'],['D2','B'],['D2','A']])
        self.assertEqual([len(p['expected']) for p in suite['documents'].values()], [8,8])

    def test_b_exact_previous_bytes_no_gold_leak_and_pair_only_role_block(self):
        b=(ex.PREVIOUS/'B-role-instruction.txt').read_bytes().decode()
        previous_schema=deepcopy(ex.read(ex.PREVIOUS/'A-request.json')['response_format'])
        def without_ids(schema):
            if isinstance(schema,dict):
                for k,v in schema.items():
                    if k=='id' and isinstance(v,dict) and 'enum' in v: v['enum']=[]
                    else: without_ids(v)
            elif isinstance(schema,list):
                for v in schema: without_ids(v)
            return schema
        previous_schema=without_ids(previous_schema)
        for p in self.suite['documents'].values():
            ex.base.verify_pair(p)
            self.assertEqual(p['roleBlocks']['B'],b)
            for arm in ('A','B'):
                payload=p['payloads'][arm]
                data=json.loads(payload['messages'][1]['content'])
                self.assertEqual(set(data),{'document','candidates'})
                self.assertEqual(payload['max_tokens'],8192)
                self.assertEqual(payload['chat_template_kwargs'],{'thinking':False})
                self.assertEqual(payload['temperature'],0)
                self.assertEqual(without_ids(deepcopy(payload['response_format'])),previous_schema)
                self.assertEqual(len(data['candidates']),8)
                for c in data['candidates']:
                    self.assertEqual(set(c),{'id','start','end','value','before','after'})
                    self.assertEqual(c['value'],p['document'][c['start']:c['end']])

    def test_changed_payload_candidate_order_and_schedule_rejected(self):
        mutations=[lambda s:s['schedule'].reverse(),
                   lambda s:s['documents']['D1']['payloads']['B'].update(max_tokens=4096),
                   lambda s:s['documents']['D1']['payloads']['B']['messages'][0].update(content='changed'),
                   lambda s:s['documents']['D2']['frozen']['candidates'].reverse(),
                   lambda s:s['documents']['D2']['payloads']['A']['response_format'].update(type='json_object')]
        for mutate in mutations:
            s=deepcopy(self.suite); mutate(s)
            with self.assertRaises(ValueError): ex.verify_suite(s)

    def test_four_fresh_requests_exact_order_shared_gate_and_duplicate_blocked(self):
        sent=[]
        def send(*args): sent.append(args[0]); return self.transport(*args)
        result=ex.run_all(self.suite,self.output,'OFFLINE-KEY',transport=send)
        self.assertEqual(sent,[self.suite['documents'][d]['payloads'][a] for d,a in ex.SCHEDULE])
        self.assertEqual(result['attempts'],4)
        self.assertEqual(result['completePairs'],['D1','D2'])
        with self.assertRaises(FileExistsError): ex.run_all(self.suite,self.output,'OFFLINE-KEY',transport=send)
        self.assertEqual(len(sent),4)

    def test_failure_at_each_call_blocks_every_later_send_and_preserves_partial_pairs(self):
        for fail_at in range(1,5):
            sub=self.output/str(fail_at); sub.mkdir()
            sent=[]
            def send(*args):
                sent.append(True)
                if len(sent)==fail_at:
                    error=ex.base.AnalysisError('INVALID_RESPONSE')
                    error.response_diagnostic={'http_status':200,'content_type':'text/event-stream','location':'sse.json'}
                    raise error
                return self.transport(*args)
            result=ex.run_all(self.suite,sub,'OFFLINE-KEY',transport=send)
            self.assertEqual(result['attempts'],fail_at)
            self.assertTrue(result['failed'])
            self.assertEqual(result['completed'],ex.SCHEDULE[:fail_at-1])
            self.assertEqual(result['completePairs'],['D1'] if fail_at>2 else [])
            doc,arm=ex.SCHEDULE[fail_at-1]
            self.assertEqual(ex.read(sub/doc/f'{arm}-diagnostic.json')['location'],'sse.json')

    def test_parser_contract_returned_model_and_encoded_secret_failures_stop_first(self):
        good=json.loads(envelope(self.suite['documents']['D1']))
        invalid_content=deepcopy(good); invalid_content['choices'][0]['message']['content']='not-json'
        missing=deepcopy(good); missing['choices'][0]['message']['content']='{"assessments":[]}'
        wrong_model=deepcopy(good); wrong_model['model']='other-model'
        secret=deepcopy(good); secret['private']='OFFLINE-KEY'
        encoded=json.dumps(secret).replace('OFFLINE-KEY',''.join('\\u%04x'%ord(c) for c in 'OFFLINE-KEY')).encode()
        for index,raw in enumerate([json.dumps(p).encode() for p in (invalid_content,missing,wrong_model)]+[encoded]):
            sub=self.output/str(index); sub.mkdir()
            sent=[]
            def send(*args): sent.append(True); return raw
            result=ex.run_all(self.suite,sub,'OFFLINE-KEY',transport=send)
            self.assertTrue(result['failed'])
            self.assertEqual(len(sent),1)
            if index==3: self.assertFalse(list(sub.rglob('*-response.json')))
            self.assertNotIn('OFFLINE-KEY',''.join(p.read_text('utf-8') for p in sub.rglob('*.json')))

    def test_shared_total_shrinks_later_requests_does_not_reset_for_second_document(self):
        now=[0.]; limits=[]
        def send(*args):
            limits.append(args[2]); now[0]+=3
            return self.transport(*args)
        result=ex.run_all(self.suite,self.output,'OFFLINE-KEY',transport=send,clock=lambda:now[0],total_seconds=12,reserve=2)
        self.assertEqual(result['error'],'PROVIDER_TIMEOUT')
        self.assertEqual(result['completePairs'],['D1'])
        self.assertEqual(len(limits),4)
        for actual,bound in zip(limits,[10,7,4,1]): self.assertLess(actual,bound)

    def test_clock_expiry_before_third_transmission_preserves_completed_pair(self):
        now=[0.]; checks=[0]; sent=[]
        def verify():
            checks[0]+=1
            if checks[0]==5: now[0]=10
        def send(*args): sent.append(True); return self.transport(*args)
        result=ex.run_all(self.suite,self.output,'OFFLINE-KEY',transport=send,verify=verify,clock=lambda:now[0],total_seconds=12,reserve=2)
        self.assertEqual(result['error'],'PROVIDER_TIMEOUT')
        self.assertEqual(len(sent),2)
        self.assertEqual(result['completePairs'],['D1'])
        self.assertEqual([r['state'] for r in ex.read(self.output/'calls.json')],['validated','validated'])

    def test_gate_rejects_fifth_out_of_order_and_post_failure_request(self):
        for d in ('D1','D2'): (self.output/d).mkdir()
        gate=ex.Gate(self.suite,self.output,self.transport,lambda:None)
        for d,a in ex.SCHEDULE: gate(self.suite['documents'][d]['payloads'][a],'OFFLINE-KEY',600)
        with self.assertRaises(ex.base.AnalysisError): gate(self.suite['documents']['D1']['payloads']['A'],'OFFLINE-KEY',600)
        self.assertEqual(len(gate.calls),4)
        gate=ex.Gate(self.suite,self.output,self.transport,lambda:None)
        with self.assertRaises(ex.base.AnalysisError): gate(self.suite['documents']['D1']['payloads']['B'],'OFFLINE-KEY',600)
        with self.assertRaises(ex.base.AnalysisError): gate(self.suite['documents']['D1']['payloads']['A'],'OFFLINE-KEY',600)
        self.assertEqual(len(gate.calls),0)

    def test_identity_mismatch_zero_sends(self):
        def verify(): raise ValueError('FROZEN_FILE_CHANGED')
        sent=[]
        result=ex.run_all(self.suite,self.output,'OFFLINE-KEY',transport=lambda *a:sent.append(True),verify=verify)
        self.assertEqual(result['attempts'],0)
        self.assertFalse(sent)

    def test_existing_subprocess_kills_stalled_request_without_network(self):
        original=subprocess.run
        def stalled(command,**kwargs):
            return original([sys.executable,'-c','import sys,time; sys.stdin.buffer.read(); time.sleep(30)'],**kwargs)
        started=time.monotonic()
        with patch('agentfit_ai.nvidia_streaming.subprocess.run',side_effect=stalled):
            with self.assertRaises(ex.base.AnalysisError) as caught:
                ex.base.post_nvidia_streaming(self.suite['documents']['D1']['payloads']['A'],'OFFLINE-KEY',.2)
        self.assertEqual(caught.exception.code,'PROVIDER_TIMEOUT')
        self.assertLess(time.monotonic()-started,3)

    def test_metrics_keep_negation_uncertainty_and_server_proposed_problem_separate(self):
        d1=ex.assess(self.suite['documents']['D1'],reply(self.suite['documents']['D1']))
        d2=ex.assess(self.suite['documents']['D2'],reply(self.suite['documents']['D2']))
        self.assertEqual(d1['metrics']['correctSupported'],5)
        self.assertEqual(d1['metrics']['correctExclusion'],2)
        self.assertEqual(d1['metrics']['correctNegative'],1)
        self.assertEqual(d2['metrics']['correctSupported'],4)
        self.assertEqual(d2['metrics']['correctUncertainty'],2)
        self.assertEqual(d2['metrics']['correctHold'],1)
        self.assertEqual(d2['metrics']['tentativeProposedExcluded'],1)
        self.assertTrue(d2['rows'][7]['conflictEvidenceSelected'])
        p=self.suite['documents']['D1']; r=reply(p)
        r['assessments'][4].update(field='external_integrations',mentionKind='external_service',modelStatus='confirmed',role='product_fact')
        bad=ex.assess(p,r)
        self.assertEqual(bad['metrics']['modelFalsePositive'],1)
        self.assertEqual(bad['metrics']['serverFalsePositive'],1)
        r['assessments'][4].update(field='other',mentionKind='other',modelStatus='confirmed')
        other=ex.assess(p,r)
        self.assertEqual(other['metrics']['otherConfirmed'],1)
        self.assertEqual(other['metrics']['correctExclusion'],1)

    def test_counter_scope_and_invalid_quote_audits_not_hidden_in_role_metric(self):
        p=self.suite['documents']['D1']; r=reply(p)
        r['assessments'][5]['counterEvidence']=[{'quote':p['expected'][7]['source'],'occurrence':0}]
        r['assessments'][6]['support'][0]['occurrence']=1
        result=ex.assess(p,r)
        self.assertEqual(result['metrics']['roleError'],0)
        self.assertEqual(result['metrics']['citationDefectCandidates'],1)
        self.assertEqual(result['metrics']['normal']['needs_confirmation'],2)
        self.assertEqual(result['metrics']['citationErrors']['occurrenceInvalid'],1)
        self.assertEqual(result['metrics']['citationErrors']['candidateNotCovered'],1)

    def test_expired_budget_before_first_request_never_sends(self):
        now=[0.]
        sent=[]
        def verify(): now[0]=10
        result=ex.run_all(self.suite,self.output,'OFFLINE-KEY',transport=lambda *a:sent.append(True),
                          verify=verify,clock=lambda:now[0],total_seconds=12,reserve=2)
        self.assertFalse(sent)
        self.assertEqual(result['attempts'],0)
        self.assertEqual(result['error'],'PROVIDER_TIMEOUT')

    def test_conflict_credit_requires_both_valid_support_and_counter_evidence(self):
        p=self.suite['documents']['D2']
        for support in ([],[{'quote':p['expected'][7]['source'],'occurrence':1}],
                        [{'quote':p['expected'][0]['source'],'occurrence':0}]):
            r=reply(p)
            r['assessments'][7]['support']=support
            result=ex.assess(p,r)
            self.assertFalse(result['rows'][7]['conflictEvidenceSelected'])
            self.assertFalse(result['rows'][7]['correctHold'])
            self.assertFalse(result['rows'][7]['correctUncertainty'])
            self.assertFalse(result['rows'][7]['statusError'])
            self.assertEqual(result['rows'][7]['citation']['errors']['candidateNotCovered'],1)

if __name__ == '__main__': unittest.main(verbosity=2)
