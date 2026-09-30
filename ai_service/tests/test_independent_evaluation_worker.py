from copy import deepcopy
import importlib
import importlib.util
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch
import unittest

from agentfit_ai.independent_profile_evaluation import score_confirmation
from agentfit_ai.solar import AnalysisError
from tests.test_independent_profile_evaluation import DOCUMENT, gold_fixture, outcome_fixture


def packet_fixture():
    return {'document': DOCUMENT, 'documentId': 'PUBLIC-01', 'solarKey': 'unit-solar-secret',
            'nvidiaKey': 'unit-nvidia-secret', 'gold': gold_fixture()}


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        name = 'agentfit_ai.independent_evaluation_protocol'
        self.assertIsNotNone(importlib.util.find_spec(name), 'score boundary not implemented')
        self.api = importlib.import_module(name)
        self.gold = gold_fixture()
        self.score = score_confirmation(DOCUMENT, 'PUBLIC-01', self.gold,
                                        outcome_fixture('frontend', ['React'], [(0, 5)]))

    def test_actual_scorer_output_is_copied_and_accepted(self):
        checked = self.api.validate_score(DOCUMENT, self.gold, self.score)
        self.assertEqual(checked, self.score)
        checked['items'].clear()
        self.assertEqual(len(self.score['items']), 1)

    def test_safe_failure_keeps_gold_denominator(self):
        score = score_confirmation(DOCUMENT, 'PUBLIC-01', self.gold,
            {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'})
        checked = self.api.validate_score(DOCUMENT, self.gold, score)
        self.assertEqual(sum(f['missing'] for f in checked['fields'].values()), 2)

    def test_rejects_raw_fields_false_counts_forged_positions_and_release_claims(self):
        mutations = [lambda s: s.update(raw='SECRET'), lambda s: s.update(error='SECRET'),
            lambda s: s.update(human_reviewed=True), lambda s: s.update(release_gate_passed=True),
            lambda s: s.update(questions=True), lambda s: s['fields']['frontend'].update(matched=2),
            lambda s: s['items'][0].update(index=8), lambda s: s['items'][0].update(unit_id='U999'),
            lambda s: s['items'][0].update(value_sha256='0'*64),
            lambda s: s['items'][0].update(occurrences=[{'start': 10, 'end': 15}]),
            lambda s: s['items'][0].update(occurrence_overflow=True),
            lambda s: s['fields']['backend'].update(missing=0),
            lambda s: s['field_states'].update(unknown=0)]
        for index, change in enumerate(mutations):
            with self.subTest(index=index):
                score = deepcopy(self.score)
                change(score)
                with self.assertRaisesRegex(ValueError, '^INVALID_SCORE$'):
                    self.api.validate_score(DOCUMENT, self.gold, score)

    def test_failure_cannot_carry_success_items(self):
        self.score.update(status='failed', error='PROVIDER_TIMEOUT')
        with self.assertRaisesRegex(ValueError, '^INVALID_SCORE$'):
            self.api.validate_score(DOCUMENT, self.gold, self.score)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        name = 'agentfit_ai.independent_evaluation_worker'
        self.assertIsNotNone(importlib.util.find_spec(name), 'evaluation worker not implemented')
        self.api = importlib.import_module(name)

    def test_worker_scores_real_outcome_and_discards_provider_stdout(self):
        def provider(document, document_id, solar_key, nvidia_key):
            self.assertEqual((document, document_id, solar_key, nvidia_key),
                (DOCUMENT, 'PUBLIC-01', 'unit-solar-secret', 'unit-nvidia-secret'))
            print('provider-private-output')
            return outcome_fixture('frontend', ['React'], [(0, 5)])
        output = io.StringIO()
        with patch.object(self.api, 'execute_integrated_analysis', side_effect=provider), redirect_stdout(output):
            result = self.api.execute_request(packet_fixture())
        self.assertEqual(result['fields']['frontend']['matched'], 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('unit-solar-secret', json.dumps(result))
        self.assertNotIn('React', json.dumps(result))

    def test_rejects_input_before_provider_call(self):
        changes = [lambda p: p.update(documentId='PUBLIC-02'), lambda p: p.update(raw='SECRET'),
            lambda p: p['gold'].update(source_sha256='0'*64), lambda p: p.update(solarKey=''),
            lambda p: p.update(solarKey=p['nvidiaKey']), lambda p: p.update(solarKey='React'),
            lambda p: p.update(nvidiaKey='x'*4097)]
        with patch.object(self.api, 'execute_integrated_analysis') as provider:
            for change in changes:
                packet = packet_fixture()
                change(packet)
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_INPUT$'):
                    self.api.execute_request(packet)
            provider.assert_not_called()

    def test_provider_errors_retain_failure_counts_without_exception_content(self):
        for error, code in [(AnalysisError('PROVIDER_TIMEOUT'), 'PROVIDER_TIMEOUT'),
                            (RuntimeError('unit-solar-secret PRIVATE'), 'ANALYSIS_FAILURE')]:
            with self.subTest(code=code), patch.object(self.api, 'execute_integrated_analysis', side_effect=error):
                result = self.api.execute_request(packet_fixture())
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['error'], code)
                self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 2)
                self.assertNotIn('PRIVATE', json.dumps(result))
