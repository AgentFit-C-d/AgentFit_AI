"""Only evidence representation changes; citation recovery must expose raw mistakes."""
import copy
import importlib.util
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'work/harness/b-evidence-selection-comparison/experiment.py'
spec = importlib.util.spec_from_file_location('b_evidence_experiment', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
runner_spec = importlib.util.spec_from_file_location('b_evidence_runner', PATH.with_name('evaluate.py'))
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)
FIXTURE = Path(__file__).parent / 'fixtures/evidence_audit/saved_pair.json'


class BEvidenceSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = json.loads(FIXTURE.read_text(encoding='utf-8'))['files']
        cls.inputs = json.loads(files['inputs.json'])
        cls.document, cls.frozen = cls.inputs['document'], cls.inputs['frozen']
        cls.registry = module.build_registry(cls.document, cls.frozen)
        cls.saved_b = json.loads(files['summary.json'])['arms']['B']['records']
        cls.b_rows = []
        for name, text in sorted(files.items()):
            if name.endswith('-B-response.json'):
                cls.b_rows.extend(json.loads(json.loads(text)['choices'][0]['message']['content'])['decisions'])

    def unit_row(self, index, **changes):
        candidate = self.registry['candidates'][index]
        row = self.b_rows[index]
        return dict({'id': row['id'], 'field': row['field'], 'status': row['status'],
                     'supportUnitIds': candidate['localUnitIds'], 'counterUnitIds': []}, **changes)

    def test_both_arms_have_identical_full_context_candidates_and_model_settings(self):
        pair = module.build_pair(self.document, self.frozen)
        self.assertIn('payloads', pair)
        self.assertEqual(len(pair['payloads']['Q']), 9)
        for index, (q, u) in enumerate(zip(pair['payloads']['Q'], pair['payloads']['U'])):
            legacy = module.build_payload('B', self.document, self.frozen['candidates'][index*8:index*8+8])
            self.assertEqual(q['messages'][1], u['messages'][1])
            context = json.loads(q['messages'][1]['content'])
            original_context = json.loads(legacy['messages'][1]['content'])
            self.assertEqual(context['document'], self.document)
            self.assertEqual(context['candidates'], original_context['candidates'])
            self.assertEqual(context['sourceRegistry']['units'], self.registry['units'])
            self.assertEqual(q['messages'][0], legacy['messages'][0])
            self.assertEqual(u['messages'][0]['content'].replace(module.UNIT_INSTRUCTION, module.QUOTE_INSTRUCTION),
                             q['messages'][0]['content'])
            for key in ('model', 'temperature', 'chat_template_kwargs', 'max_tokens'):
                self.assertEqual(q[key], legacy[key])
                self.assertEqual(u[key], legacy[key])
            qp = q['response_format']['json_schema']['schema']['properties']['decisions']['items']['properties']
            up = u['response_format']['json_schema']['schema']['properties']['decisions']['items']['properties']
            for key in ('id', 'field', 'status'):
                self.assertEqual(qp[key], up[key])

    def test_legacy_b_replays_unchanged_with_twenty_two_citation_defects(self):
        records, diagnostics = module.normalize('Q', self.document, self.registry,
                                                 self.frozen['candidates'], self.b_rows)
        self.assertEqual(records, self.saved_b)
        self.assertEqual(sum(d['citationDefect'] for d in diagnostics), 22)
        score = module.score_rows(records, self.inputs['gold']['cases'], [r['id'] for r in records])
        self.assertEqual((score['raw_false_confirmed'], score['false_supported'], score['normal_missing'], score['held_total']),
                         (4, 3, 2, 37))

    def test_schema_keeps_status_after_evidence_in_both_arms(self):
        pair = module.build_pair(self.document, self.frozen)
        q, u = (pair['payloads'][a][0]['response_format']['json_schema']['schema']
                ['properties']['decisions']['items'] for a in ('Q', 'U'))
        original_names = {'supportUnitIds': 'support', 'counterUnitIds': 'counterEvidence'}
        self.assertEqual([original_names.get(k, k) for k in u['properties']], list(q['properties']))
        self.assertEqual([original_names.get(k, k) for k in u['required']], q['required'])

    def test_fixed_responses_recover_tag_but_also_expose_clean_ui_false_admission(self):
        batch = self.frozen['candidates'][4:6]
        q, qd = module.normalize('Q', self.document, self.registry, batch, self.b_rows[4:6])
        u, ud = module.normalize('U', self.document, self.registry, batch, [self.unit_row(4), self.unit_row(5)])
        self.assertEqual([r['verdict'] for r in q], ['needs_confirmation', 'needs_confirmation'])
        self.assertEqual([r['verdict'] for r in u], ['supported', 'supported'])
        gold = [{'id': 'C004', 'field': None}, {'id': 'C005', 'field': 'features'}]
        for records in (q, u):
            self.assertEqual(module.score_rows(records, gold, ['C004', 'C005'])['raw_false_confirmed'], 1)
        self.assertEqual(module.score_rows(q, gold, ['C004', 'C005'])['false_supported'], 0)
        self.assertEqual(module.score_rows(u, gold, ['C004', 'C005'])['false_supported'], 1)
        self.assertEqual(module.score_rows(u, gold, ['C004', 'C005'])['normal_missing'], 0)
        self.assertEqual([d['citationDefect'] for d in qd], [True, True])
        self.assertEqual([d['citationDefect'] for d in ud], [False, False])

    def test_invalid_units_hold_candidate_without_hiding_raw_false_confirmation(self):
        index = 4
        heading = self.registry['units'][next(i for i,u in enumerate(self.registry['units'])
                                             if u['kind'] == 'heading')]['unitId']
        local = self.registry['candidates'][index]['localUnitIds'][0]
        for selected in [['unknown'], [local, local], [heading], []]:
            raw = self.unit_row(index, supportUnitIds=selected)
            records, diagnostic = module.normalize('U', self.document, self.registry,
                [self.frozen['candidates'][index]], [raw])
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['raw_status'], 'confirmed')
            self.assertEqual(records[0]['verdict'], 'needs_confirmation')
            self.assertTrue(diagnostic[0]['citationDefect'])
            self.assertEqual(diagnostic[0]['originalResponse'], raw)

    def test_counterevidence_prevents_admission_without_changing_classification(self):
        row = self.unit_row(5, counterUnitIds=self.registry['candidates'][4]['localUnitIds'])
        records, diagnostic = module.normalize('U', self.document, self.registry,
                                               [self.frozen['candidates'][5]], [row])
        self.assertEqual(records[0]['verdict'], 'needs_confirmation')
        self.assertFalse(diagnostic[0]['citationDefect'])
        self.assertEqual(records[0]['raw_status'], 'confirmed')

    def test_malformed_classification_or_candidate_set_stops_instead_of_scoring_partial(self):
        for change in ({'field': 'invented'}, {'status': 'approved'}, {'id': 'foreign'},
                       {'supportUnitIds': [1]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.normalize('U', self.document, self.registry, [self.frozen['candidates'][5]],
                                  [self.unit_row(5, **change)])

    def _simulate(self, output, failure=None, free_failure=False):
        pair = module.build_pair(self.document, self.frozen)
        calls = []
        def transport(payload, _key, _timeout):
            calls.append(payload)
            if len(calls) == failure:
                raise module.AnalysisError('PROVIDER_RATE_LIMIT')
            context = json.loads(payload['messages'][1]['content'])
            ids = [r['id'] for r in context['candidates']]
            props = payload['response_format']['json_schema']['schema']['properties']['decisions']['items']['properties']
            unit_mode = 'supportUnitIds' in props
            rows = []
            for cid in ids:
                index = next(i for i, c in enumerate(self.frozen['candidates']) if c['id'] == cid)
                rows.append(self.unit_row(index) if unit_mode else self.b_rows[index])
            return json.dumps({'model': module.MODEL, 'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps({'decisions': rows})}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}).encode()
        def check_free():
            if free_failure:
                raise ValueError('FREE_ACCESS_UNCONFIRMED')
        gate = module.CallGate(output / 'calls', check_free=check_free, check_identity=lambda: None,
                               transport=transport)
        sender = module.NvidiaAnalyzer('offline-placeholder', transport=gate)
        with patch('builtins.print'):
            report = module.run_pair(output, self.inputs, pair, gate, sender)
        return report, calls

    def test_mock_pair_finishes_eighteen_calls_and_keeps_all_raw_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            report, calls = self._simulate(Path(temp))
        self.assertTrue(report.get('comparable'))
        self.assertEqual(len(calls), 18)
        self.assertEqual(report['calls_started'], 18)
        for arm in ('Q', 'U'):
            self.assertEqual(len(report['arms'][arm]['records']), 68)
            self.assertEqual(len(report['arms'][arm]['evidence']), 68)
            self.assertEqual(report['arms'][arm]['metrics']['retained'], 68)
        self.assertEqual(report['arms']['Q']['metrics']['citation_defects'], 22)
        self.assertEqual(report['arms']['U']['metrics']['raw_false_confirmed'], 4)
        self.assertGreaterEqual(report['arms']['U']['metrics']['false_supported'], 4)
        self.assertFalse(report['service_applied'])
        self.assertFalse(report['large_goal_resumed'])

    def test_first_failure_stops_pair_without_retry_or_partial_score(self):
        with tempfile.TemporaryDirectory() as temp:
            report, calls = self._simulate(Path(temp), failure=3)
        self.assertFalse(report['comparable'])
        self.assertEqual(len(calls), 3)
        self.assertEqual(report['retries'], 0)
        self.assertIsNone(report['arms']['Q']['metrics'])
        self.assertIsNone(report['arms']['U']['metrics'])
        self.assertEqual(len(report['arms']['Q']['records']), 16)
        self.assertEqual(report['arms']['U']['calls'], 0)

    def test_unconfirmed_free_scope_makes_zero_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            report, calls = self._simulate(Path(temp), free_failure=True)
        self.assertEqual(calls, [])
        self.assertEqual(report['calls_started'], 0)
        self.assertEqual(report['arms']['Q']['error'], 'FREE_ACCESS_UNCONFIRMED')

    def test_frozen_b_payload_keeps_source_gold_and_same_context_then_prevents_refreeze(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, free, output = root / 'source', root / 'free.json', root / 'output'
            source.mkdir()
            files = json.loads(FIXTURE.read_text(encoding='utf-8'))['files']
            (source / 'inputs.json').write_bytes(files['inputs.json'].encode('utf-8'))
            free.write_text(json.dumps({'version': 'nvidia-free-access-v1',
                'confirmed_no_additional_charge': True,
                'endpoint': 'https://integrate.api.nvidia.com/v1/chat/completions',
                'models': [module.MODEL, 'z-ai/glm-5.3'], 'expires_at': '2099-01-01T00:00:00Z',
                'max_model_calls': 64, 'evidence': 'synthetic offline fixture only'}), encoding='utf-8')
            result = runner.freeze(output, source=source, free=free)
            self.assertEqual(result.get('max_calls'), 18)
            self.assertEqual((output / 'inputs.json').read_bytes(), (source / 'inputs.json').read_bytes())
            self.assertEqual(json.loads((output / 'inputs.json').read_text(encoding='utf-8')), self.inputs)
            runner.check_identity(output)
            with self.assertRaises(FileExistsError):
                runner.freeze(output, source=source, free=free)
            with patch.object(runner, 'load_nvidia_key') as key, patch.object(runner, 'post_nvidia_streaming') as net:
                (output / 'live-started.json').write_text('{}', encoding='utf-8')
                with self.assertRaises(FileExistsError):
                    runner.live(output)
                key.assert_not_called()
                net.assert_not_called()
            with (output / 'pair.json').open('ab') as handle:
                handle.write(b'\n')
            with self.assertRaisesRegex(ValueError, 'FROZEN_INPUT_OR_CODE_CHANGED'):
                runner.check_identity(output)

    def test_free_failure_during_pair_stops_before_next_transport(self):
        calls, checks = [], []
        def check_free():
            checks.append(1)
            if len(checks) == 2:
                raise ValueError('FREE_ACCESS_UNCONFIRMED')
        with tempfile.TemporaryDirectory() as temp:
            gate = module.CallGate(Path(temp), check_free=check_free, check_identity=lambda: None,
                                   transport=lambda *args: calls.append(1) or b'{}')
            gate.begin_arm('A')
            gate({'model': module.MODEL}, 'offline', 600)
            with self.assertRaises(ValueError):
                gate({'model': module.MODEL}, 'offline', 600)
            self.assertEqual(len(calls), 1)
            self.assertTrue(gate.stopped)


if __name__ == '__main__':
    unittest.main()
