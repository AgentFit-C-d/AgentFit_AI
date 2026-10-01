"""Offline contract tests: no model calls and no claim about prompt effectiveness."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / 'work/harness/classification-instruction-evaluation'
SPEC = ROOT / 'specs/ai-developer/classification-instruction-evaluation'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClassificationInstructionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HARNESS / 'compare.py').exists(), 'comparison harness not implemented')
        self.m = load(HARNESS / 'compare.py', 'instruction_compare_test')
        self.guidance = (SPEC / 'classification-guidance-draft.txt').read_bytes().decode('utf-8')
        self.inputs = json.loads((SPEC / 'candidates-draft.json').read_text(encoding='utf-8'))
        self.gold = json.loads((SPEC / 'gold-draft.json').read_text(encoding='utf-8'))['cases']

    def fixture(self, doc_id='FR'):
        doc = next(d for d in self.inputs['documents'] if d['docId'] == doc_id)
        source = (SPEC / doc['sourceFile']).read_bytes().decode('utf-8')
        gold = [g for g in self.gold if g['docId'] == doc_id]
        pair = self.m.build_instruction_pair(source, doc['frozen'], self.guidance)
        rows = [{'id': g['candidateId'], 'field': g['expectedField'] or 'other',
                 'status': g['expectedStatus'], 'supportUnitIds': g['localUnitIds'],
                 'counterUnitIds': []} for g in gold]
        return source, doc['frozen'], gold, pair, rows

    def test_payloads_only_differ_in_approved_classification_suffix(self):
        for doc_id in ('FR', 'LS'):
            source, frozen, gold, pair, _ = self.fixture(doc_id)
            prior = self.m.baseline.build_pair(source, frozen)['payloads']['U']
            self.assertEqual(pair['payloads']['U'], prior)
            for u, c in zip(prior, pair['payloads']['U+C'], strict=True):
                expected = copy.deepcopy(u)
                expected['messages'][0]['content'] += '\n' + self.guidance
                self.assertEqual(json.dumps(c), json.dumps(expected))
                schema = c['response_format']['json_schema']['schema']['properties']['decisions']['items']
                self.assertEqual(list(schema['properties']),
                                 ['id', 'field', 'supportUnitIds', 'counterUnitIds', 'status'])
                self.assertEqual(schema['required'], list(schema['properties']))
                context = json.loads(c['messages'][1]['content'])
                self.assertEqual(context['document'], source)
                self.assertEqual(context['sourceRegistry']['units'], pair['registry']['units'])
                self.assertNotIn('expectedField', c['messages'][1]['content'])
                for g in gold:
                    self.assertNotIn(g['reason'], c['messages'][1]['content'])

    def test_correct_fixtures_keep_positives_exclusions_and_ambiguity_separate(self):
        for doc_id, positives, exclusions in [('FR', 10, 5), ('LS', 6, 9)]:
            source, frozen, gold, pair, rows = self.fixture(doc_id)
            records, diagnostics = self.m.baseline.normalize('U', source, pair['registry'], frozen['candidates'], rows)
            metrics = self.m.score_instruction_rows(records, diagnostics, gold)
            self.assertEqual((metrics['raw_false_confirmed'], metrics['false_supported'],
                              metrics['raw_normal_missing'], metrics['normal_missing'],
                              metrics['citation_defects']), (0, 0, 0, 0, 0))
            self.assertEqual(metrics['positive_gold'], positives)
            self.assertEqual(metrics['correct_excluded'], exclusions)
            self.assertEqual((metrics['scored'], metrics['total'], metrics['held_total'],
                              metrics['held_ambiguous']), (15, 16, 1, 1))

    def test_citation_failure_does_not_hide_raw_false_confirmation(self):
        source, frozen, gold, pair, rows = self.fixture()
        g = next(g for g in gold if g['caseId'] == 'FR03')
        row = next(r for r in rows if r['id'] == g['candidateId'])
        row.update(field='features', status='confirmed', supportUnitIds=['wrong-unit'])
        records, diagnostics = self.m.baseline.normalize('U', source, pair['registry'], frozen['candidates'], rows)
        metrics = self.m.score_instruction_rows(records, diagnostics, gold)
        self.assertEqual((metrics['raw_false_confirmed'], metrics['false_supported'],
                          metrics['citation_defects']), (1, 0, 1))
        row['supportUnitIds'] = g['localUnitIds']
        records, diagnostics = self.m.baseline.normalize('U', source, pair['registry'], frozen['candidates'], rows)
        self.assertEqual(self.m.score_instruction_rows(records, diagnostics, gold)['false_supported'], 1)

    def test_negated_fact_confirmed_is_false_even_with_correct_field(self):
        source, frozen, gold, pair, rows = self.fixture('LS')
        g = next(g for g in gold if g['caseId'] == 'LS07')
        next(r for r in rows if r['id'] == g['candidateId'])['status'] = 'confirmed'
        records, diagnostics = self.m.baseline.normalize('U', source, pair['registry'], frozen['candidates'], rows)
        metrics = self.m.score_instruction_rows(records, diagnostics, gold)
        self.assertEqual((metrics['raw_false_confirmed'], metrics['false_supported']), (1, 1))

    def test_ambiguous_cases_are_reported_but_not_scored_as_false_positive(self):
        source, frozen, gold, pair, rows = self.fixture('LS')
        g = next(g for g in gold if not g['scored'])
        next(r for r in rows if r['id'] == g['candidateId']).update(field='features', status='confirmed')
        records, diagnostics = self.m.baseline.normalize('U', source, pair['registry'], frozen['candidates'], rows)
        metrics = self.m.score_instruction_rows(records, diagnostics, gold)
        self.assertEqual(metrics['raw_false_confirmed'], 0)
        detail = next(d for d in metrics['details'] if d['caseId'] == 'LS15')
        self.assertFalse(detail['scored'])
        self.assertEqual(detail['actual']['raw_status'], 'confirmed')
        self.assertTrue(detail['actual']['support'])

    def test_all_held_and_missing_outputs_preserve_denominators(self):
        source, frozen, gold, pair, rows = self.fixture()
        for row in rows:
            row['status'] = 'tentative'
        records, diagnostics = self.m.baseline.normalize('U', source, pair['registry'], frozen['candidates'], rows)
        metrics = self.m.score_instruction_rows(records, diagnostics, gold)
        self.assertEqual((metrics['normal_missing'], metrics['held_normal'], metrics['held_total']), (10, 10, 16))
        self.assertEqual(metrics['core_positive_supported'], 0)
        missing = self.m.score_instruction_rows(records[:8], diagnostics[:8], gold)
        self.assertEqual((missing['total'], missing['retained'], missing['unassessable']), (16, 8, 8))
        self.assertFalse(missing['complete'])
        self.assertEqual(missing['citation_unassessable'], 8)

    def test_same_fixed_outputs_score_identically_for_both_arms(self):
        source, frozen, gold, pair, rows = self.fixture()
        results = [self.m.score_instruction_rows(*self.m.baseline.normalize(
            'U', source, pair['registry'], frozen['candidates'], copy.deepcopy(rows)), gold) for _ in range(2)]
        self.assertEqual(results[0], results[1])

    def gate(self, root, transport, check_free=lambda: None, check_identity=lambda: None):
        jobs = [{'docId':'D', 'arm':'U', 'batch':i+1, 'payload':{'model': self.m.MODEL, 'n':i}}
                for i in range(8)]
        gate = self.m.EightCallGate(Path(root)/'calls', jobs, check_free=check_free,
                                   check_identity=check_identity, transport=transport)
        return gate, jobs

    def test_gate_never_calls_a_ninth_time_and_preserves_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, jobs = self.gate(tmp, lambda p,k,t: b'{}')
            for job in jobs:
                gate(job['payload'], 'test-key', 600)
            with self.assertRaises(ValueError):
                gate(jobs[-1]['payload'], 'test-key', 600)
            self.assertEqual(gate.started, 8)
            self.assertEqual(len(list((Path(tmp)/'calls').glob('*-started.json'))), 8)
            self.assertEqual(len(list((Path(tmp)/'calls').glob('*-response.json'))), 8)

    def test_gate_stops_without_network_when_free_identity_or_payload_invalid(self):
        def forbidden(*args):
            self.fail('external transport must not be reached')
        def fail():
            raise ValueError('FREE_ACCESS_UNCONFIRMED')
        for failure in ('free', 'identity', 'payload'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                gate, jobs = self.gate(tmp, forbidden, check_free=fail if failure=='free' else lambda:None,
                                       check_identity=fail if failure=='identity' else lambda:None)
                payload = dict(jobs[0]['payload'])
                if failure == 'payload':
                    payload['n'] = 99
                with self.assertRaises(ValueError):
                    gate(payload, 'test-key', 600)
                self.assertEqual(gate.started, 0)
                self.assertTrue(gate.stopped)

    def test_gate_quota_or_call_failure_is_terminal_without_retry(self):
        for code in ('PROVIDER_RATE_LIMIT', 'PROVIDER_UNAVAILABLE'):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                def fail(*args):
                    raise self.m.AnalysisError(code)
                gate, jobs = self.gate(tmp, fail)
                with self.assertRaises(self.m.AnalysisError):
                    gate(jobs[0]['payload'], 'test-key', 600)
                with self.assertRaises(ValueError):
                    gate(jobs[0]['payload'], 'test-key', 600)
                self.assertEqual(gate.started, 1)
                self.assertEqual(gate.stop_reason, code)
                self.assertEqual(len(list((Path(tmp)/'calls').glob('*-finished.json'))), 1)

    def test_run_stops_on_first_malformed_batch_without_losing_remaining_candidates(self):
        self.assertTrue((HARNESS/'evaluate.py').exists(), 'runner not implemented')
        runner = load(HARNESS/'evaluate.py', 'instruction_runner_test')
        package = runner.prepare_package(SPEC)
        with tempfile.TemporaryDirectory() as tmp:
            def transport(payload, key, timeout):
                return json.dumps({'model':self.m.MODEL,'choices':[{'message':{'content':
                    json.dumps({'decisions':[]})},'finish_reason':'stop'}],
                    'usage':{'prompt_tokens':1,'completion_tokens':1}}).encode()
            gate = self.m.EightCallGate(Path(tmp)/'calls', package['jobs'], check_free=lambda:None,
                                        check_identity=lambda:None, transport=transport)
            sender = self.m.baseline.NvidiaAnalyzer('test-key', transport=gate, model=self.m.MODEL)
            report = runner.run_package(Path(tmp), package, gate, sender)
            self.assertFalse(report['comparable'])
            self.assertEqual(report['calls_started'], 1)
            self.assertEqual(report['documents']['FR']['U']['prompt_tokens'], 1)
            self.assertEqual(report['documents']['FR']['U']['completion_tokens'], 1)
            self.assertEqual(sum(a['metrics']['unassessable'] for d in report['documents'].values()
                                 for a in d.values()), 64)

    def test_valid_responses_without_usage_finish_eight_calls_and_preserve_unknown(self):
        runner = load(HARNESS/'evaluate.py', 'instruction_runner_test')
        package = runner.prepare_package(SPEC)
        with tempfile.TemporaryDirectory() as tmp:
            def transport(payload, key, timeout):
                body = json.loads(payload['messages'][1]['content'])
                source = next(d for d in package['documents'].values() if d['document'] == body['document'])
                ids = [c['candidateId'] for c in body['sourceRegistry']['candidates']]
                rows = [{'id':g['candidateId'], 'field':g['expectedField'] or 'other',
                         'status':g['expectedStatus'], 'supportUnitIds':g['localUnitIds'],
                         'counterUnitIds':[]} for g in source['gold'] if g['candidateId'] in ids]
                return json.dumps({'model':self.m.MODEL,'choices':[{'message':{'content':
                    json.dumps({'decisions':rows})},'finish_reason':'stop'}]}).encode()
            gate = self.m.EightCallGate(Path(tmp)/'calls', package['jobs'],check_free=lambda:None,
                                        check_identity=lambda:None,transport=transport)
            sender = self.m.baseline.NvidiaAnalyzer('test-key',transport=gate,model=self.m.MODEL)
            try:
                report = runner.run_package(Path(tmp),package,gate,sender)
            except TypeError as exc:
                self.fail('valid replies without usage must produce a report: '+str(exc))
            self.assertTrue(report['comparable'])
            self.assertEqual(report['calls_started'], 8)
            for doc in report['documents'].values():
                for arm in doc.values():
                    self.assertIsNone(arm['prompt_tokens'])
                    self.assertIsNone(arm['completion_tokens'])
                    self.assertEqual(arm['prompt_tokens_unknown_calls'], 2)
                    self.assertEqual(arm['prompt_tokens_known_sum'], 0)
                    self.assertEqual(arm['metrics']['normal_missing'], 0)

    def test_package_has_exact_schedule_and_does_not_send_gold(self):
        self.assertTrue((HARNESS/'evaluate.py').exists(), 'runner not implemented')
        runner = load(HARNESS/'evaluate.py', 'instruction_runner_test')
        package = runner.prepare_package(SPEC)
        self.assertEqual([(j['docId'], j['arm'], j['batch']) for j in package['jobs']],
            [('FR','U',1),('FR','U',2),('FR','U+C',1),('FR','U+C',2),
             ('LS','U+C',1),('LS','U+C',2),('LS','U',1),('LS','U',2)])
        for job in package['jobs']:
            payload = json.dumps(job['payload'], ensure_ascii=False)
            self.assertNotIn('expectedField', payload)
            self.assertNotIn('human_review', payload)


if __name__ == '__main__':
    unittest.main()
