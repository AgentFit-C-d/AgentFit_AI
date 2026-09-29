import unittest

from agentfit_ai.recoverable_solar_evaluation import solar_factory
from agentfit_ai.recoverable_solar_analysis import RecoverableSolarAnalyzer


class RecoverableSolarEvaluationTests(unittest.TestCase):
    def test_factory_uses_service_settings_despite_anchored_runner_options(self):
        analyzer = solar_factory("synthetic-key", transport=lambda *_: b"",
                                 model="solar-pro4", prompt_revision="v2",
                                 review_effort="medium", analysis_timeout_seconds=60)
        self.assertIsInstance(analyzer, RecoverableSolarAnalyzer)
        self.assertEqual(analyzer._analysis_timeout_seconds, 40)
        self.assertTrue(analyzer._evidence_contract)
        self.assertTrue(analyzer._semantic_review)


if __name__ == "__main__":
    unittest.main()
