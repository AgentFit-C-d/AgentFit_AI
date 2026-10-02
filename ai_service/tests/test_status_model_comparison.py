"""Offline contract tests. Fixture responses are not model quality evidence."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT/'work/harness/status-model-comparison'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StatusModelTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HARNESS/'experiment.py').exists(), 'model-only harness missing')
        self.m = load(HARNESS/'experiment.py', 'model_experiment_test')
        old = self.m.status
        self.saved = old.prepare_package(old.previous.prepare_package(old.previous.SPEC))
        self.package = self.m.build_model_pair(self.saved)

    def response(self, payload, **overrides):
        body = json.loads(payload['messages'][1]['content'])
        source = next(d for d in self.package['documents'].values() if d['document']==body['document'])
        ids = [c['candidateId'] for c in body['sourceRegistry']['candidates']]
        rows = [{'id':g['candidateId'],'field':g['expectedField'] or 'other','status':g['expectedStatus'],
                 'supportUnitIds':g['localUnitIds'],'counterUnitIds':[]}
                for g in source['gold'] if g['candidateId'] in ids]
        envelope = {'model':payload['model'], 'choices':[{'finish_reason':'stop',
                    'message':{'content':json.dumps({'decisions':rows})}}]}
        envelope.update(overrides)
        return json.dumps(envelope).encode()

    def gate(self, tmp, transport, **kwargs):
        return self.m.ModelCallGate(Path(tmp)/'calls',self.package['jobs'],
            transport=transport, check_free=kwargs.pop('check_free',lambda:5400),
            check_identity=kwargs.pop('check_identity',lambda:None),**kwargs)

    def test_pair_changes_model_only_preserving_full_messages_schema_and_gold(self):
        self.assertEqual([(j['docId'],j['arm'],j['batch']) for j in self.package['jobs']],
            [('FR','G',1),('FR','D',1),('FR','D',2),('FR','G',2),
             ('LS','D',1),('LS','G',1),('LS','G',2),('LS','D',2)])
        for job in self.package['jobs']:
            payload=job['payload']
            source=self.saved['documents'][job['docId']]
            expected=copy.deepcopy(source['pair']['payloads']['US'][job['batch']-1])
            expected['model']=self.m.MODELS[job['arm']]
            self.assertEqual(json.dumps(payload),json.dumps(expected))
            self.assertEqual(self.package['documents'][job['docId']]['gold'],source['gold'])
            self.assertNotIn('expectedField',payload['messages'][1]['content'])
            self.assertNotIn('human_review',payload['messages'][1]['content'])

    def test_sender_does_not_apply_existing_glm_tuning(self):
        captured=[]
        def transport(payload,key,timeout):
            captured.append(copy.deepcopy(payload))
            return self.response(payload)
        sender=self.m.FixedPayloadSender('test-key',transport)
        for arm in ('G','D'):
            payload=next(j['payload'] for j in self.package['jobs'] if j['arm']==arm)
            reply,model,_,_=sender._send_payload(payload,('decisions',),timeout=600)
            self.assertEqual(captured[-1],payload)
            self.assertEqual(captured[-1]['temperature'],0)
            self.assertEqual(captured[-1]['chat_template_kwargs'],{'thinking':False})
            self.assertNotIn('reasoning_effort',captured[-1])
            self.assertEqual(model,payload['model'])
            self.assertEqual(len(reply['decisions']),8)

    def test_exact_eight_calls_and_wire_payload_without_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate=self.gate(tmp,lambda p,k,t:self.response(p))
            for job in self.package['jobs']:
                gate(job['payload'],'test-key',600)
            with self.assertRaises(ValueError): gate(self.package['jobs'][0]['payload'],'test-key',600)
            self.assertEqual(gate.started,8)
            for i,job in enumerate(self.package['jobs'],1):
                wire=Path(tmp)/'calls'/f'{i:02d}-wire-request.json'
                expected={**job['payload'],'stream':True}
                self.assertEqual(json.loads(wire.read_text(encoding='utf-8')),expected)
                self.assertNotIn('test-key',wire.read_text(encoding='utf-8'))

    def test_free_identity_or_payload_error_never_sends(self):
        def forbidden(*args): self.fail('network must not be reached')
        def fail(): raise ValueError('FREE_ACCESS_UNCONFIRMED')
        for kind in ('free','identity','payload'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                gate=self.gate(tmp,forbidden,check_free=fail if kind=='free' else lambda:5400,
                               check_identity=fail if kind=='identity' else lambda:None)
                payload=copy.deepcopy(self.package['jobs'][0]['payload'])
                if kind=='payload': payload['temperature']=0.5
                with self.assertRaises(ValueError): gate(payload,'test-key',600)
                self.assertEqual(gate.started,0)
                self.assertTrue(gate.stopped)

    def test_deadline_limits_entire_request_and_prevents_next_call(self):
        tick=[0.0]; limits=[]
        def transport(payload,key,timeout): limits.append(timeout); return self.response(payload)
        with tempfile.TemporaryDirectory() as tmp:
            gate=self.gate(tmp,transport,clock=lambda:tick[0])
            tick[0]=5399.5
            gate(self.package['jobs'][0]['payload'],'test-key',600)
            self.assertLessEqual(limits[0],0.5)
            tick[0]=5400
            with self.assertRaises(ValueError): gate(self.package['jobs'][1]['payload'],'test-key',600)
            self.assertEqual(gate.started,1)

    def test_request_timeout_quota_option_and_provider_failures_are_terminal(self):
        for code in ('PROVIDER_TIMEOUT','PROVIDER_RATE_LIMIT','PROVIDER_REQUEST','PROVIDER_UNAVAILABLE'):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as tmp:
                def fail(*args): raise self.m.AnalysisError(code)
                gate=self.gate(tmp,fail)
                with self.assertRaises(self.m.AnalysisError): gate(self.package['jobs'][0]['payload'],'test-key',600)
                with self.assertRaises(ValueError): gate(self.package['jobs'][0]['payload'],'test-key',600)
                self.assertEqual((gate.started,gate.stop_reason),(1,code))

    def runner(self):
        self.assertTrue((HARNESS/'evaluate.py').exists(),'model runner missing')
        return load(HARNESS/'evaluate.py','model_runner_test')

    def test_failures_preserve_response_and_stop_remaining_seven_calls(self):
        runner=self.runner()
        for kind in ('model','parse','schema','length'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                def transport(payload,key,timeout):
                    env=json.loads(self.response(payload))
                    if kind=='model': env['model']='alias'
                    if kind=='parse': env['choices'][0]['message']['content']='bad-json'
                    if kind=='schema': env['choices'][0]['message']['content']='{"decisions":[]}'
                    if kind=='length': env['choices'][0]['finish_reason']='length'
                    return json.dumps(env).encode()
                gate=self.gate(tmp,transport)
                report=runner.run_package(Path(tmp),self.package,gate,self.m.FixedPayloadSender('test-key',gate))
                self.assertFalse(report['comparable'])
                self.assertEqual((report['calls_started'],report['unstarted_calls']),(1,7))
                self.assertTrue((Path(tmp)/'calls/01-response.json').exists())
                self.assertIsNone(report['documents']['FR']['G']['comparison_metrics'])

    def test_full_fixed_response_pair_preserves_score_and_ambiguous_cases(self):
        runner=self.runner()
        with tempfile.TemporaryDirectory() as tmp:
            gate=self.gate(tmp,lambda p,k,t:self.response(p))
            report=runner.run_package(Path(tmp),self.package,gate,self.m.FixedPayloadSender('test-key',gate))
            self.assertTrue(report['comparable'])
            self.assertEqual(report['calls_started'],8)
            for doc,arms in report['documents'].items():
                self.assertEqual(arms['D']['metrics'],arms['G']['metrics'])
                for a in arms.values():
                    self.assertIsNone(a['prompt_tokens'])
                    self.assertEqual((a['metrics']['normal_missing'],a['metrics']['citation_defects']),(0,0))
                    self.assertEqual(a['metrics']['held_ambiguous'],1)
                    self.assertEqual(a['metrics']['correct_excluded'],5 if doc=='FR' else 9)
            ls=report['documents']['LS']['G']['diagnostics']['special_cases']
            self.assertEqual((ls['LS07']['raw_field'],ls['LS07']['raw_status']),('features','negated'))
            self.assertFalse(ls['LS15']['scored'])

    def test_all_held_is_not_mistaken_for_successful_classification(self):
        totals={'normal_missing':0,'correct_excluded':0,'raw_false_confirmed':0,'held_normal':0}
        for source in self.package['documents'].values():
            rows=[{'id':g['candidateId'],'field':g['expectedField'] or 'other','status':'tentative',
                   'supportUnitIds':g['localUnitIds'],'counterUnitIds':[]} for g in source['gold']]
            records,evidence=self.m.compare.baseline.normalize('U',source['document'],source['pair']['registry'],source['frozen']['candidates'],rows)
            metrics=self.m.compare.score_instruction_rows(records,evidence,source['gold'])
            for key in totals: totals[key]+=metrics[key]
        self.assertEqual(totals,{'normal_missing':16,'correct_excluded':0,'raw_false_confirmed':0,'held_normal':16})

    def test_scope_is_fresh_scoped_and_expires_without_extension(self):
        now=datetime.now(timezone.utc)
        scope={'version':'status-model-free-v1','confirmed_at':now.isoformat(),
               'expires_at':(now+timedelta(minutes=30)).isoformat(),'confirmed_by':'user',
               'confirmed_no_additional_charge':True,'endpoint':self.m.ENDPOINT,
               'models':list(self.m.MODELS.values()),'max_calls':8,'retries':0,
               'no_paid_fallback':True}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'scope.json'
            for change in ({},{'version':'nvidia-free-access-v1'},{'confirmed_no_additional_charge':False},
                           {'expires_at':(now-timedelta(seconds=1)).isoformat()},
                           {'models':['z-ai/glm-5.3']},{'max_calls':9},{'endpoint':'https://paid.example'}):
                path.write_text(json.dumps({**scope,**change}),encoding='utf-8')
                if change:
                    with self.assertRaises(ValueError): self.m.check_free(path,now=now)
                else: self.assertEqual(self.m.check_free(path,now=now),1800)

    def test_existing_live_marker_blocks_before_key_or_network(self):
        runner=self.runner()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'live-started.json').write_text('{}')
            with self.assertRaises(FileExistsError): runner.live(Path(tmp))

    def test_declared_schema_array_limit_stops_after_first_response(self):
        runner=self.runner()
        with tempfile.TemporaryDirectory() as tmp:
            def transport(payload,key,timeout):
                env=json.loads(self.response(payload))
                body=json.loads(env['choices'][0]['message']['content'])
                row=body['decisions'][0]
                row['supportUnitIds']=row['supportUnitIds']*9
                env['choices'][0]['message']['content']=json.dumps(body)
                return json.dumps(env).encode()
            gate=self.gate(tmp,transport)
            report=runner.run_package(Path(tmp),self.package,gate,self.m.FixedPayloadSender('test-key',gate))
            self.assertFalse(report['comparable'])
            self.assertEqual(report['calls_started'],1)
            self.assertEqual(report['stop_error'],'INVALID_UNIT_DECISIONS')
            self.assertTrue((Path(tmp)/'FR-G-01-parsed.json').exists())

    def test_free_expiry_during_hash_verification_does_not_send(self):
        tick=[0]
        def free():
            if tick[0]>=10: raise ValueError('FREE_ACCESS_UNCONFIRMED')
            return 10-tick[0]
        def identity(): tick[0]=11
        def forbidden(*args): self.fail('expired request reached transport')
        with tempfile.TemporaryDirectory() as tmp:
            gate=self.gate(tmp,forbidden,check_free=free,check_identity=identity,clock=lambda:tick[0])
            with self.assertRaises(ValueError): gate(self.package['jobs'][0]['payload'],'test-key',600)
            self.assertEqual(gate.started,0)

    def test_final_gate_includes_record_write_time(self):
        from unittest.mock import patch
        tick=[0]; limits=[]
        original=self.m.write_json
        def delayed_write(path,value):
            original(path,value)
            tick[0]+=1
        with tempfile.TemporaryDirectory() as tmp:
            gate=self.gate(tmp,lambda p,k,t:limits.append(t) or self.response(p),
                           check_free=lambda:10-tick[0],clock=lambda:tick[0])
            with patch.object(self.m,'write_json',delayed_write):
                gate(self.package['jobs'][0]['payload'],'test-key',600)
            self.assertEqual(limits,[7])


if __name__=='__main__': unittest.main()
