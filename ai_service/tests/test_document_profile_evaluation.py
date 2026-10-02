"""Offline preparation and transparent, source-complete analysis observation."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from test_candidate_analysis_pipeline import ProviderFixture


def evaluation():
    try:
        return importlib.import_module('diagnostic_tools.document_profile_evaluation')
    except ModuleNotFoundError as error:
        if error.name != 'diagnostic_tools.document_profile_evaluation':
            raise
        raise AssertionError('document profile preparation is not implemented') from None


class DocumentProfileEvaluationTests(unittest.TestCase):
    def test_prepare_keeps_raw_unicode_and_cannot_open_network(self):
        module = evaluation()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'plan.md'
            source.write_bytes(b'\xef\xbb\xbf' + '# Demo\r\n기록 😀\r\n'.encode())
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('no network')):
                result = module.prepare_document(source)
            self.assertEqual(result['document'], '# Demo\r\n기록 😀\r\n')
            self.assertEqual(result['kind'], 'MARKDOWN')
            self.assertEqual(result['characterCount'], 14)
            self.assertNotEqual(result['sourceSha256'], result['textSha256'])

    def test_default_run_only_prepares_and_does_not_load_keys(self):
        module = evaluation()
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'plan.md', Path(folder) / 'result'
            source.write_bytes(b'# Demo\r\n')
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('no network')):
                result = module.run_document_evaluation(source, output)
            self.assertEqual(result['status'], 'prepared_not_executed')
            self.assertEqual(result['actualModelCalls'], 0)
            self.assertEqual((output / 'source.md').read_bytes(), source.read_bytes())
            self.assertEqual(result['limits']['maxCalls'], 64)
            self.assertEqual(result['limits']['totalSeconds'], 1800)
            self.assertEqual(result['limits']['retries'], 0)
            with self.assertRaisesRegex(ValueError, 'LIVE_EXECUTION_NOT_APPROVED'):
                module.run_document_evaluation(source, Path(folder) / 'live', execute=True)
            with self.assertRaises(FileExistsError):
                module.run_document_evaluation(source, output)

    def test_detailed_observation_preserves_legacy_events_payloads_and_results(self):
        # Captures raw source proposals and curation; does not inject evaluation gold.
        baseline, observed = ProviderFixture(), ProviderFixture()
        expected = baseline.run()
        events, details = [], []
        try:
            result = observed.run(observer=lambda s, p: events.append((s, p)),
                                  detail_observer=lambda s, p: details.append((s, p)))
        except TypeError:
            self.fail('pipeline has no opt-in detail observation')
        self.assertEqual(result, expected)
        self.assertEqual(observed.requests, baseline.requests)
        self.assertEqual([s for s, _ in events], ['grounded', 'classified', 'reviewed', 'projected'])
        by_stage = dict(details)
        self.assertEqual(by_stage['general_extracted'][0].extraction_text, 'TestApp')
        self.assertEqual(len(by_stage['operations_grounded']['candidates']), 32)
        self.assertEqual(len(by_stage['grounding_inputs']['general']['candidates']), 10)
        self.assertEqual(len(by_stage['review_completed']['labels']), 41)
        self.assertEqual(len(by_stage['feature_curated']['curation']['groups']), 2)
        # Observation receives copies; retained objects cannot alter analysis.
        by_stage['review_completed']['labels'].clear()
        self.assertEqual(result, expected)

    def test_failure_preserves_completed_review_before_curation(self):
        case, details = ProviderFixture(fail_name='agentfit_feature_grouping'), []
        from agentfit_ai.candidate_first_profile import CandidatePipelineError
        try:
            with self.assertRaises(CandidatePipelineError):
                case.run(detail_observer=lambda s, p: details.append((s, p)))
        except TypeError:
            self.fail('pipeline has no opt-in detail observation')
        self.assertIn('review_completed', dict(details))
        self.assertNotIn('feature_curated', dict(details))

    def test_call_estimate_depends_on_candidates_not_gold_features(self):
        module = evaluation()
        # 2 SDK chunks + 1 operations + ceil(40/8) + ceil(25/20) + 1 coverage.
        self.assertEqual(module.estimate_calls(2, 40, 25, False)['total'], 11)
        # At most four existing curation calls, including its conditional repair.
        self.assertEqual(module.estimate_calls(2, 240, 240, True)['total'], 50)


if __name__ == '__main__':
    unittest.main()
