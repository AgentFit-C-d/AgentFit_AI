"""Offline payload/retention tests; fake transport does not establish model quality."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT/'work/harness/status-definition-unification'
SPEC = ROOT/'specs/ai-developer/status-definition-unification'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StatusDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HARNESS/'experiment.py').exists(), 'status-only comparison not implemented')
        self.m = load(HARNESS/'experiment.py', 'status_experiment_test')
        self.prior = self.m.previous.prepare_package(self.m.previous.SPEC)
        self.package = self.m.prepare_package(self.prior)

    def test_only_authorized_status_regions_change_in_real_payloads(self):
        edits = json.loads((SPEC/'status-edits.json').read_text(encoding='utf-8'))
        definition = (SPEC/'status-definition.txt').read_bytes().decode('utf-8')
        for doc_id, source in self.package['documents'].items():
            old = self.prior['documents'][doc_id]
            self.assertEqual(source['gold'], old['gold'])
            self.assertEqual(source['frozen'], old['frozen'])
            self.assertEqual(source['document'], old['document'])
            self.assertEqual(source['pair']['registry'], old['pair']['registry'])
            self.assertEqual(source['pair']['payloads']['UC'], old['pair']['payloads']['U+C'])
            for uc, us in zip(source['pair']['payloads']['UC'], source['pair']['payloads']['US'], strict=True):
                rest = copy.deepcopy(us)
                rest['messages'][0]['content'] = uc['messages'][0]['content']
                self.assertEqual(json.dumps(rest), json.dumps(uc))
                text = us['messages'][0]['content']
                self.assertEqual(text.count(definition), 1)
                # Reversing the reviewed edit regions must recover the full original.
                reverse = text.replace(definition, edits[0]['old'], 1)
                for edit in edits[1:]:
                    reverse = reverse.replace(edit['anchor'], edit['old']+edit['anchor'], 1)
                self.assertEqual(reverse, uc['messages'][0]['content'])
                self.assertNotIn('expectedStatus', us['messages'][1]['content'])

    def test_changed_or_duplicate_status_boundary_is_rejected(self):
        system = self.prior['documents']['FR']['pair']['payloads']['U+C'][0]['messages'][0]['content']
        edits = json.loads((SPEC/'status-edits.json').read_text(encoding='utf-8'))
        for mutated in (system.replace(edits[0]['old'], 'unreviewed status', 1), system+edits[0]['old']):
            with self.assertRaises(ValueError):
                self.m.unify_status(mutated)

    def test_schedule_and_schema_are_unchanged_except_named_arms(self):
        self.assertEqual([(j['docId'],j['arm'],j['batch']) for j in self.package['jobs']],
                         [('FR','UC',1),('FR','UC',2),('FR','US',1),('FR','US',2),
                          ('LS','US',1),('LS','US',2),('LS','UC',1),('LS','UC',2)])
        for job in self.package['jobs']:
            old = next(j for j in self.prior['jobs'] if j['docId']==job['docId'] and j['arm']=='U+C' and j['batch']==job['batch'])
            self.assertEqual(job['payload']['response_format'],old['payload']['response_format'])

    def rows(self, doc='LS'):
        source = self.package['documents'][doc]
        rows = [{'id':g['candidateId'],'field':g['expectedField'] or 'other','status':g['expectedStatus'],
                 'supportUnitIds':g['localUnitIds'],'counterUnitIds':[]} for g in source['gold']]
        return source, rows

    def test_server_keeps_negation_uncertainty_and_other_confirmed_raw(self):
        source, rows = self.rows()
        ids = {g['caseId']:g['candidateId'] for g in source['gold']}
        next(r for r in rows if r['id']==ids['LS01']).update(field='other',status='confirmed')
        original = copy.deepcopy(rows)
        records, evidence = self.m.compare.baseline.normalize('U',source['document'],source['pair']['registry'],source['frozen']['candidates'],rows)
        by_id = {r['id']:r for r in records}
        self.assertEqual((by_id[ids['LS07']]['raw_field'],by_id[ids['LS07']]['raw_status'],by_id[ids['LS07']]['verdict']),('features','negated','excluded'))
        self.assertEqual(by_id[ids['LS15']]['verdict'],'needs_confirmation')
        self.assertEqual((by_id[ids['LS01']]['raw_field'],by_id[ids['LS01']]['raw_status'],by_id[ids['LS01']]['verdict']),('other','confirmed','needs_confirmation'))
        self.assertEqual(rows,original)
        self.assertEqual({e['id']:e['originalResponse'] for e in evidence},{r['id']:r for r in original})
        self.assertEqual([r['id'] for r in records],[c['id'] for c in source['frozen']['candidates']])
        self.assertEqual(len(records),16)

    def test_diagnostics_distinguishes_wrong_counter_from_review_line_230(self):
        source, rows = self.rows()
        g = next(g for g in source['gold'] if g['caseId']=='LS15')
        target = next(r for r in rows if r['id']==g['candidateId'])
        target.update(field='other',status='confirmed')
        units = source['pair']['registry']['units']
        lines = source['document'].splitlines(keepends=True)
        at230 = sum(map(len,lines[:229]))
        correct = next(u['unitId'] for u in units if u['start']==at230)
        wrong = next(u['unitId'] for u in units if u['start']==0)
        for chosen,want in (([],False),([wrong],False),([correct],True)):
            target['counterUnitIds'] = chosen
            records,_ = self.m.compare.baseline.normalize('U',source['document'],source['pair']['registry'],source['frozen']['candidates'],rows)
            diag = self.m.diagnostics(records,source['gold'],source['document'])
            self.assertEqual(diag['other_confirmed_total'],1)
            self.assertEqual(diag['other_confirmed_scored'],0)
            case = diag['special_cases']['LS15']
            self.assertEqual(case['raw_status'],'confirmed')
            self.assertEqual(next(x for x in case['review_lines'] if x['line']==230)['selected_as_counter'],want)

    def test_mock_run_preserves_all_rows_and_reports_usage_without_relabeling(self):
        self.assertTrue((HARNESS/'evaluate.py').exists(),'runner not implemented')
        runner = load(HARNESS/'evaluate.py','status_runner_test')
        with tempfile.TemporaryDirectory() as tmp:
            def transport(payload,key,timeout):
                body = json.loads(payload['messages'][1]['content'])
                doc = next(d for d in self.package['documents'].values() if d['document']==body['document'])
                ids = [c['id'] for c in body['candidates']]
                rows = [{'id':g['candidateId'],'field':g['expectedField'] or 'other','status':g['expectedStatus'],
                         'supportUnitIds':g['localUnitIds'],'counterUnitIds':[]} for g in doc['gold'] if g['candidateId'] in ids]
                return json.dumps({'model':self.m.MODEL,'choices':[{'message':{'content':json.dumps({'decisions':rows})},'finish_reason':'stop'}]}).encode()
            gate = self.m.compare.EightCallGate(Path(tmp)/'calls',self.package['jobs'],check_free=lambda:None,check_identity=lambda:None,transport=transport)
            sender = self.m.previous.NvidiaAnalyzer('test-key',transport=gate,model=self.m.MODEL)
            report = runner.run_package(Path(tmp),self.package,gate,sender)
            self.assertTrue(report['comparable'])
            self.assertEqual(report['calls_started'],8)
            for doc in report['documents'].values():
                self.assertEqual(set(doc),{'UC','US'})
                for result in doc.values():
                    self.assertEqual(result['metrics']['retained'],16)
                    self.assertEqual(result['metrics']['normal_missing'],0)
                    self.assertIsNone(result['prompt_tokens'])
                    self.assertEqual(result['prompt_tokens_unknown_calls'],2)
            self.assertEqual(report['documents']['LS']['UC']['diagnostics']['special_cases']['LS07']['raw_status'],'negated')

    def test_free_failure_or_provider_failure_stops_remaining_batches(self):
        runner = load(HARNESS/'evaluate.py','status_runner_failure_test')
        for mode,expected in (('free',0),('provider',1),('invalid_reply',1)):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                def free():
                    if mode=='free': raise ValueError('FREE_ACCESS_UNCONFIRMED')
                def transport(*args):
                    if mode=='provider': raise self.m.compare.AnalysisError('PROVIDER_RATE_LIMIT')
                    return json.dumps({'model':self.m.MODEL,'choices':[{'message':{'content':'{"decisions":[]}'},'finish_reason':'stop'}]}).encode()
                gate = self.m.compare.EightCallGate(Path(tmp)/'calls',self.package['jobs'],check_free=free,check_identity=lambda:None,transport=transport)
                sender = self.m.previous.NvidiaAnalyzer('test-key',transport=gate,model=self.m.MODEL)
                report = runner.run_package(Path(tmp),self.package,gate,sender)
                self.assertEqual(report['calls_started'],expected)
                self.assertEqual(report['retries'],0)
                self.assertFalse(report['comparable'])
                self.assertEqual(sum(a['metrics']['unassessable'] for d in report['documents'].values() for a in d.values()),64)

    def test_second_live_invocation_is_refused_before_any_key_or_network(self):
        runner = load(HARNESS/'evaluate.py','status_runner_reentry_test')
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'live-started.json').write_text('{}',encoding='utf-8')
            with self.assertRaises(FileExistsError):
                runner.live(Path(tmp))


if __name__ == '__main__':
    unittest.main()
