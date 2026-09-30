"""Input credentials must be rejected before any extraction or provider boundary."""
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from agentfit_ai.candidate_analysis_pipeline import analyze_integrated_candidates
from agentfit_ai.solar import AnalysisError
from test_candidate_analysis_pipeline import ProviderFixture, SOLAR_KEY, NVIDIA_KEY


class IntegratedInputGuardTests(unittest.TestCase):
    def setUp(self):
        self.extractor = Mock(side_effect=AssertionError('unexpected extraction'))
        self.solar = Mock(side_effect=AssertionError('unexpected Solar request'))
        self.nvidia = Mock(side_effect=AssertionError('unexpected NVIDIA request'))
        self.observer = Mock()

    def invoke(self, document='Invented record service', document_id='DOC', **options):
        return analyze_integrated_candidates(document, document_id, SOLAR_KEY, NVIDIA_KEY,
            **dict({'extractor': self.extractor, 'solar_transport': self.solar,
                    'nvidia_transport': self.nvidia, 'observer': self.observer}, **options))

    def blocked(self, **options):
        error = None
        try:
            self.invoke(**options)
        except Exception as caught:
            error = caught
        self.assertEqual(self.extractor.call_count, 0)
        self.solar.assert_not_called()
        self.nvidia.assert_not_called()
        self.observer.assert_not_called()
        self.assertIsInstance(error, AnalysisError)
        self.assertEqual(error.code, 'SENSITIVE_CONTENT')
        self.assertEqual(str(error), 'SENSITIVE_CONTENT')

    def test_existing_sensitive_patterns_block_document_and_id_before_extractor(self):
        examples = ['password=synthetic-password-only', 'API_KEY: "synthetic-key-only"',
                    'access_token=synthetic-token-only', 'secret=synthetic-secret-only',
                    '-----BEGIN PRIVATE KEY-----', 'sk-' + 'x' * 24, 'ghp_' + 'A' * 24]
        for index, value in enumerate(examples):
            for target in ('document', 'document_id'):
                with self.subTest(index=index, target=target):
                    self.extractor.reset_mock()
                    self.blocked(**{target: value})

    def test_default_langextract_path_is_also_blocked_before_generation(self):
        with patch('agentfit_ai.langextract_solar_trial.extract_candidates',
                   side_effect=AssertionError('unexpected default extraction')) as extract:
            error = None
            try:
                self.invoke(document='password=synthetic-password-only', extractor=None)
            except Exception as caught:
                error = caught
            extract.assert_not_called()
            self.assertIsInstance(error, AnalysisError)
            self.assertEqual(error.code, 'SENSITIVE_CONTENT')
        self.solar.assert_not_called()
        self.nvidia.assert_not_called()

    def test_blocked_input_does_not_change_existing_collectors(self):
        trace, reviews = [{'prior': True}], [{'prior_review': True}]
        original = deepcopy((trace, reviews))
        self.blocked(document='password=synthetic-password-only',
                     call_trace=trace, review_calls=reviews)
        self.assertEqual((trace, reviews), original)

    def test_normal_text_with_credential_field_names_preserves_whole_profile(self):
        expected = ProviderFixture(1).run()
        fixture = ProviderFixture(1)
        fixture.document += '\nThe password field is required. API key entry is manual.'
        self.assertEqual(fixture.run(), expected)
        self.assertEqual(len(fixture.requests), 4)

    def test_existing_key_and_invalid_option_rejections_still_precede_io(self):
        cases = [{'document': key} for key in (SOLAR_KEY, NVIDIA_KEY)]
        cases += [{'document_id': key} for key in (SOLAR_KEY, NVIDIA_KEY)]
        cases += [{'document': ' '}, {'nvidia_retry_limit': True}, {'max_calls': 0}]
        for index, options in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.invoke(**options)
        for boundary in (self.extractor, self.solar, self.nvidia, self.observer):
            boundary.assert_not_called()


if __name__ == '__main__':
    unittest.main()
