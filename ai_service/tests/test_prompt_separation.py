import unittest
from unittest.mock import Mock
from agentfit_ai.solar import SolarAnalyzer
from test_staged_analysis import response, core, features

class PromptSeparationTests(unittest.TestCase):
    def run_analysis(self, replies):
        transport = Mock(side_effect=[response(reply) for reply in replies])
        result = SolarAnalyzer("synthetic-key", transport=transport).analyze(
            "Alpha Python registration", "doc-1")
        prompts = [call.args[0]["messages"][0]["content"] for call in transport.call_args_list]
        return result, prompts

    def assert_core_only(self, prompt):
        self.assertIn("external_integrations", prompt)
        self.assertIn("project_name", prompt)
        self.assertNotIn("absenceLineIds", prompt)
        self.assertNotIn('"quote"', prompt)

    def assert_features_only(self, prompt):
        self.assertIn("absenceLineIds", prompt)
        self.assertIn('"quote"', prompt)
        self.assertNotIn("external_integrations", prompt)
        self.assertNotIn("project_name", prompt)
        self.assertNotIn("evidenceLineIds", prompt)

    def test_extraction_instructions_are_scoped_to_the_call(self):
        result, prompts = self.run_analysis([core(), features()])
        self.assert_core_only(prompts[0])
        self.assert_features_only(prompts[1])
        self.assertEqual(result.profile["data"]["features"], ["registration"])
        self.assertEqual(result.provider_calls, 2)

    def test_feature_repair_keeps_only_feature_instructions(self):
        result, prompts = self.run_analysis([core(), features(99), features()])
        self.assert_features_only(prompts[2])
        self.assertEqual(result.provider_calls, 3)

    def test_core_repair_keeps_only_core_instructions(self):
        bad = core()
        bad["backend"] = {"value": ["Python"], "evidenceLineIds": [99]}
        repair = {"backend": {"value": ["Python"], "evidenceLineIds": [1]}}
        result, prompts = self.run_analysis([bad, features(), repair])
        self.assert_core_only(prompts[2])
        self.assertEqual(result.profile["data"]["backend"], ["Python"])

    def test_mixed_repair_includes_both_rules_in_one_call(self):
        bad = core()
        bad["backend"] = {"value": ["Python"], "evidenceLineIds": [99]}
        repair = dict(features(), backend={"value": ["Python"], "evidenceLineIds": [1]})
        result, prompts = self.run_analysis([bad, features(99), repair])
        self.assertIn("external_integrations", prompts[2])
        self.assertIn("absenceLineIds", prompts[2])
        self.assertEqual(result.provider_calls, 3)
        self.assertEqual(set(result.repaired_fields), {"backend", "features"})
