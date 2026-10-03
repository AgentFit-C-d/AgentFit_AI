"""Offline preflight only; synthetic calls are never experiment quality scores."""
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
from test_mention_role_cause import recorded_batches


def reply(package):
    by_id={row['id']:row for batch in recorded_batches('v3') for row in batch['raw']}
    rows=[by_id[c['id']] for c in package['frozen']['candidates']]
    return json.dumps({'model':ex.MODEL,'choices':[{'finish_reason':'stop','message':{
        'role':'assistant','content':json.dumps({'assessments':rows},ensure_ascii=False)}}]},ensure_ascii=False).encode('utf-8')


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package=ex.build_package()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ex.ROOT/'tmp')
        self.output=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        guard=offline()
        guard.__enter__()
        self.addCleanup(guard.__exit__,None,None,None)

    def test_exact_eight_source_spans_and_only_role_block_diff(self):
        ex.verify_pair(self.package)
        self.assertEqual(tuple(c['id'] for c in self.package['frozen']['candidates']),ex.IDS)
        from agentfit_ai.candidate_mention_roles import MENTION_ROLE_INSTRUCTION
        self.assertEqual(MENTION_ROLE_INSTRUCTION,self.package['roleBlocks']['A'])
        for arm in ('A','B'):
            data=json.loads(self.package['payloads'][arm]['messages'][1]['content'])
            self.assertEqual(set(data),{'document','candidates'})
            self.assertEqual(len(data['document']),7796)
            self.assertNotIn('expected',data)
            self.assertEqual(self.package['payloads'][arm]['chat_template_kwargs'],{'thinking':False})
            self.assertEqual(self.package['payloads'][arm]['max_tokens'],8192)

    def test_other_options_context_schema_and_instructions_tamper_rejected(self):
        for mutate in (lambda p:p['payloads']['B'].update(temperature=1),
                       lambda p:p['payloads']['B']['messages'][0].update(content='changed'),
                       lambda p:p['payloads']['B']['messages'][1].update(content='{}'),
                       lambda p:p['payloads']['B']['response_format'].update(type='json_object')):
            changed=deepcopy(self.package)
            mutate(changed)
            with self.assertRaises(ValueError): ex.verify_pair(changed)

    def test_success_is_two_fresh_sends_in_order_and_duplicate_pair_is_blocked(self):
        seen=[]
        def send(payload,key,timeout):
            seen.append(payload)
            self.assertLessEqual(timeout,600)
            return reply(self.package)
        result=ex.run_pair(self.package,self.output,'OFFLINE-KEY',transport=send)
        self.assertEqual(seen,[self.package['payloads']['A'],self.package['payloads']['B']])
        self.assertEqual(result['completedArms'],['A','B'])
        self.assertEqual(result['attempts'],2)
        with self.assertRaises(FileExistsError):
            ex.run_pair(self.package,self.output,'OFFLINE-KEY',transport=send)
        self.assertEqual(len(seen),2)

    def test_first_transport_failure_blocks_b_and_preserves_diagnostic_without_key(self):
        seen=[]
        def send(*args):
            seen.append(True)
            error=ex.AnalysisError('INVALID_RESPONSE')
            error.response_diagnostic={'http_status':200,'content_type':'text/event-stream','location':'sse.json'}
            raise error
        result=ex.run_pair(self.package,self.output,'OFFLINE-KEY',transport=send)
        self.assertEqual(len(seen),1)
        self.assertEqual(result['unmeasuredArms'],['A','B'])
        self.assertEqual(ex.read(self.output/'A-diagnostic.json')['location'],'sse.json')
        self.assertNotIn('OFFLINE-KEY',''.join(p.read_text(encoding='utf-8') for p in self.output.glob('*.json')))

    def test_first_parser_or_server_contract_failure_blocks_b(self):
        for content in ('not-json',json.dumps({'assessments':[]})):
            sub=self.output/str(len(list(self.output.iterdir())))
            sub.mkdir()
            calls=[]
            def send(*args):
                calls.append(True)
                return json.dumps({'model':ex.MODEL,'choices':[{'finish_reason':'stop','message':{'content':content}}]}).encode()
            result=ex.run_pair(self.package,sub,'OFFLINE-KEY',transport=send)
            self.assertTrue(result['failed'])
            self.assertEqual(len(calls),1)
            self.assertFalse((sub/'B-started.json').exists())

    def test_identity_failure_prevents_any_send(self):
        seen=[]
        def changed(): raise ValueError('FROZEN_FILE_CHANGED')
        result=ex.run_pair(self.package,self.output,'OFFLINE-KEY',transport=lambda *a:seen.append(True),verify=changed)
        self.assertTrue(result['failed'])
        self.assertEqual(result['attempts'],0)
        self.assertFalse(seen)

    def test_clock_shrinks_second_request_and_preserves_finish_reserve(self):
        now=[0.0]
        timeouts=[]
        def send(payload,key,timeout):
            timeouts.append(timeout)
            now[0]+=8 if len(timeouts)==1 else 1
            return reply(self.package)
        result=ex.run_pair(self.package,self.output,'OFFLINE-KEY',transport=send,
                           clock=lambda:now[0],total_seconds=12,reserve=2)
        self.assertFalse(result['failed'])
        self.assertLess(timeouts[0],10)
        self.assertLess(timeouts[1],2)
        self.assertLessEqual(result['elapsedSeconds'],10)

    def test_expired_total_prevents_b_even_after_valid_a_response(self):
        now=[0.0]
        seen=[]
        def send(*args):
            seen.append(True)
            now[0]=10
            return reply(self.package)
        result=ex.run_pair(self.package,self.output,'OFFLINE-KEY',transport=send,
                           clock=lambda:now[0],total_seconds=12,reserve=2)
        self.assertEqual(result['error'],'PROVIDER_TIMEOUT')
        self.assertEqual(len(seen),1)
        self.assertTrue((self.output/'A-response.json').exists())

    def test_gate_cannot_send_third_or_retry_after_failure(self):
        gate=ex.PairGate(self.package,self.output,lambda *a:reply(self.package),lambda:None)
        for arm in ('A','B'): gate(self.package['payloads'][arm],'OFFLINE-KEY',600)
        with self.assertRaises(ex.AnalysisError): gate(self.package['payloads']['A'],'OFFLINE-KEY',600)
        self.assertEqual(len(gate.calls),2)

    def test_process_request_timeout_uses_real_child_termination_without_network(self):
        original=subprocess.run
        def stalled_child(command,**kwargs):
            return original([sys.executable,'-c','import sys,time; sys.stdin.buffer.read(); time.sleep(30)'],**kwargs)
        started=time.monotonic()
        with patch('agentfit_ai.nvidia_streaming.subprocess.run',side_effect=stalled_child):
            with self.assertRaises(ex.AnalysisError) as caught:
                ex.post_nvidia_streaming(self.package['payloads']['A'],'OFFLINE-KEY',.2)
        self.assertEqual(caught.exception.code,'PROVIDER_TIMEOUT')
        self.assertLess(time.monotonic()-started,3)

    def test_scoring_distinguishes_roles_grounding_and_unique_meanings(self):
        parsed=json.loads(json.loads(reply(self.package))['choices'][0]['message']['content'])
        result=ex.assess(self.package,parsed)
        self.assertEqual(result['metrics']['normal7']['supported'],1)
        self.assertEqual(result['metrics']['normal7']['needs_confirmation'],6)
        self.assertEqual(result['metrics']['serverFalsePositive'],1)
        self.assertEqual(result['metrics']['roleError'],4)
        self.assertEqual(result['metrics']['citationDefectCandidates'],2)
        self.assertEqual(result['metrics']['uniqueNormal3'],{'project_name':False,'project_type':False,'external_integrations':True})


if __name__=='__main__': unittest.main(verbosity=2)
