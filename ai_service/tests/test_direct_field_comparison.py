"""Offline safety and scoring for the isolated one-pair classification trial."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / 'work/harness/direct-field-comparison/comparison.py'
spec = importlib.util.spec_from_file_location('direct_comparison', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0, str(PATH.parent))
runner_spec = importlib.util.spec_from_file_location('direct_evaluate', PATH.parent / 'evaluate.py')
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)


def inputs():
    document = 'Cedar uses Pebble for storage. Pebble remains under review.'
    start = document.index('Pebble')
    frozen = {'candidates': [{'id': 'C000', 'start': start, 'end': start + 6}], 'rejected': []}
    return document, frozen


def row(**changes):
    return dict({'id': 'C000', 'field': 'database', 'status': 'confirmed',
                 'support': [{'quote': 'Cedar uses Pebble for storage.', 'occurrence': 0}],
                 'counterEvidence': []}, **changes)


class DirectFieldComparisonTests(unittest.TestCase):
    def _run_fixture(self, folder, fail_at=None, free_failure=False, invalid_status=False):
        document = ' '.join(f'item{i:03}' for i in range(68))
        frozen = {'candidates': [{'id': f'C{i:03}', 'start': i*8, 'end': i*8+7}
                                 for i in range(68)], 'rejected': []}
        gold = [{'id': 'C000', 'start': 0, 'end': 7, 'field': 'database'},
                {'id': 'C001', 'start': 8, 'end': 15, 'field': None}]
        payloads = {arm: [module.build_payload(arm, document, frozen['candidates'][i:i+8])
                         for i in range(0, 68, 8)] for arm in ('A', 'B')}
        calls = []
        def transport(payload, _key, _timeout):
            calls.append(payload)
            if fail_at == len(calls):
                raise module.AnalysisError('PROVIDER_UNAVAILABLE')
            name = payload['response_format']['json_schema']['schema']['required'][0]
            ids = [c['id'] for c in json.loads(payload['messages'][1]['content'])['candidates']]
            rows = []
            for cid in ids:
                positive = cid == 'C000'
                r = {'id': cid, 'field': 'database' if positive else 'other',
                     'support': [{'quote': document, 'occurrence': 0}], 'counterEvidence': []}
                if name == 'assessments':
                    r.update(modelStatus='confirmed' if positive else 'irrelevant',
                             mentionKind='other', scope='target', time='current', polarity='positive',
                             commitment='adopted', role='product_fact' if positive else 'non_product',
                             conflictsChecked=True)
                else:
                    r['status'] = 'confirmed' if positive else 'irrelevant'
                rows.append(r)
            if invalid_status:
                rows[0]['modelStatus' if name == 'assessments' else 'status'] = 'approved'
            return json.dumps({'model': module.MODEL, 'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps({name: rows})}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}).encode()
        def check_free():
            if free_failure:
                raise ValueError('FREE_ACCESS_UNCONFIRMED')
        gate = module.CallGate(folder / 'calls', check_free=check_free, check_identity=lambda: None,
                               transport=transport)
        sender = runner.NvidiaAnalyzer('local-test-placeholder', transport=gate)
        with patch('builtins.print'):
            result = runner.run_pair(folder, {'document': document, 'frozen': frozen,
                'gold': {'cases': gold}}, payloads, gate, sender)
        return result, calls

    def test_fixed_response_pair_completes_eighteen_calls_and_projection(self):
        with tempfile.TemporaryDirectory() as folder:
            result, calls = self._run_fixture(Path(folder))
            self.assertTrue(result['comparable'])
            self.assertEqual(len(calls), 18)
            for arm in ('A', 'B'):
                self.assertEqual(result['arms'][arm]['metrics']['normal_missing'], 0)
                self.assertEqual(result['arms'][arm]['projection_metrics']['normal_missing'], 0)
                self.assertEqual(result['arms'][arm]['metrics']['retained'], 68)

    def test_failure_stops_pair_and_never_scores_partial_arm(self):
        with tempfile.TemporaryDirectory() as folder:
            result, calls = self._run_fixture(Path(folder), fail_at=2)
            self.assertFalse(result['comparable'])
            self.assertEqual(len(calls), 2)
            self.assertIsNone(result['arms']['A']['metrics'])
            self.assertIsNone(result['arms']['B']['metrics'])
            self.assertEqual(len(result['arms']['A']['records']), 8)

    def test_free_preflight_reason_survives_provider_parser_without_a_call(self):
        with tempfile.TemporaryDirectory() as folder:
            result, calls = self._run_fixture(Path(folder), free_failure=True)
            self.assertEqual(calls, [])
            self.assertEqual(result['arms']['A']['error'], 'FREE_ACCESS_UNCONFIRMED')
            self.assertEqual(result['arms']['A']['provider_failures'], 0)

    def test_local_schema_error_remains_distinct_and_stops_after_one_call(self):
        with tempfile.TemporaryDirectory() as folder:
            result, calls = self._run_fixture(Path(folder), invalid_status=True)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result['arms']['A']['error'], 'INVALID_SEMANTIC_ASSESSMENT')
            self.assertIsNone(result['arms']['A']['metrics'])

    def test_arms_receive_identical_full_document_and_occurrence_context(self):
        document = '앞' * 300 + '\r\n🚀Pebble\r\n' + '뒤' * 300
        start = document.index('Pebble')
        candidates = [{'id': 'C000', 'start': start, 'end': start + 6}]
        a, b = [module.build_payload(arm, document, candidates) for arm in ('A', 'B')]
        context = json.loads(a['messages'][1]['content'])
        self.assertEqual(a['messages'][1]['content'], b['messages'][1]['content'])
        self.assertEqual(context['document'], document)
        self.assertEqual(context['candidates'][0]['before'], document[start-240:start])
        self.assertEqual(context['candidates'][0]['after'], document[start+6:start+246])
        for request in (a, b):
            self.assertEqual(request['chat_template_kwargs'], {'thinking': False})
            self.assertEqual(request['model'], module.MODEL)
            self.assertNotIn('reasoning_effort', request)

    def test_valid_direct_field_keeps_source_but_never_grants_human_approval(self):
        doc, frozen = inputs()
        checked = module.validate_direct(doc, frozen, [row()])
        self.assertEqual(checked[0]['verdict'], 'supported')
        self.assertEqual(checked[0]['sourceValue'], 'Pebble')
        self.assertNotIn('userConfirmed', checked[0])

    def test_ambiguity_bad_grounding_and_counterevidence_remain_held(self):
        doc, frozen = inputs()
        for changes in ({'status': 'tentative'}, {'support': []},
                        {'support': [{'quote': 'absent quote', 'occurrence': 0}]},
                        {'support': [{'quote': 'Pebble', 'occurrence': 1}]},
                        {'counterEvidence': [{'quote': 'Pebble remains under review.', 'occurrence': 0}]},
                        {'field': 'other'}):
            with self.subTest(changes=changes):
                self.assertEqual(module.validate_direct(doc, frozen, [row(**changes)])[0]['verdict'], 'needs_confirmation')

    def test_grounded_irrelevance_is_excluded_without_deleting_record(self):
        doc, frozen = inputs()
        checked = module.validate_direct(doc, frozen, [row(field='other', status='irrelevant')])
        self.assertEqual(checked[0]['verdict'], 'excluded')
        self.assertEqual(checked[0]['id'], 'C000')

    def test_missing_duplicate_extra_and_foreign_fields_fail_the_batch(self):
        doc, frozen = inputs()
        for rows in ([], [row(), row()], [row(id='C999')], [row(userConfirmed=True)],
                     [row(field='invented')], [row(status='approved')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                module.validate_direct(doc, frozen, rows)

    def test_all_held_is_counted_as_normal_missing_and_unnecessary_hold(self):
        checked = [{'id': 'C000', 'raw_field': 'database', 'raw_status': 'tentative',
                    'verdict': 'needs_confirmation'}]
        gold = [{'id': 'C000', 'field': 'database'}]
        score = module.score_rows(checked, gold, ['C000'])
        self.assertEqual(score['false_supported'], 0)
        self.assertEqual(score['normal_missing'], 1)
        self.assertEqual(score['held_normal'], 1)
        self.assertEqual(score['held_total'], 1)

    def test_wrong_field_counts_both_false_proposal_and_normal_miss(self):
        checked = [{'id': 'C000', 'raw_field': 'external_integrations', 'raw_status': 'confirmed',
                    'verdict': 'supported'}]
        score = module.score_rows(checked, [{'id': 'C000', 'field': 'backend'}], ['C000'])
        self.assertEqual((score['false_supported'], score['normal_missing']), (1, 1))
        with self.assertRaises(ValueError):
            module.score_rows([], [{'id': 'C000', 'field': 'backend'}], ['C000'])

    def test_gate_refuses_nineteenth_call_and_records_eighteen_started(self):
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            gate = module.CallGate(Path(folder), check_free=lambda: None,
                check_identity=lambda: None, transport=lambda *args: calls.append(args[0]) or b'{}')
            gate.begin_arm('A')
            for _ in range(18):
                gate({'model': module.MODEL}, 'local-test-placeholder', 600)
            with self.assertRaises(ValueError):
                gate({'model': module.MODEL}, 'local-test-placeholder', 600)
            self.assertEqual(len(calls), 18)
            self.assertEqual(len(list(Path(folder).glob('*-started.json'))), 18)

    def test_free_access_failure_prevents_any_transport(self):
        calls = []
        def unconfirmed():
            raise ValueError('FREE_ACCESS_UNCONFIRMED')
        with tempfile.TemporaryDirectory() as folder:
            gate = module.CallGate(Path(folder), check_free=unconfirmed, check_identity=lambda: None,
                                   transport=lambda *args: calls.append(args))
            gate.begin_arm('A')
            with self.assertRaises(ValueError):
                gate({'model': module.MODEL}, 'local-test-placeholder', 600)
            self.assertEqual(calls, [])

    def test_provider_failure_stops_all_further_calls_without_retry(self):
        calls = []
        def failed(*args):
            calls.append(1)
            raise module.AnalysisError('PROVIDER_RATE_LIMIT')
        with tempfile.TemporaryDirectory() as folder:
            gate = module.CallGate(Path(folder), check_free=lambda: None,
                                   check_identity=lambda: None, transport=failed)
            gate.begin_arm('A')
            with self.assertRaises(module.AnalysisError):
                gate({'model': module.MODEL}, 'local-test-placeholder', 600)
            with self.assertRaises(ValueError):
                gate({'model': module.MODEL}, 'local-test-placeholder', 600)
            self.assertEqual(calls, [1])


if __name__ == '__main__':
    unittest.main()
