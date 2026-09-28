import json
import unittest
from unittest.mock import Mock

from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from test_staged_analysis import response


class CandidateModelRoutingTests(unittest.TestCase):
    def test_nvidia_handles_only_candidate_generation(self):
        solar_models = []
        nvidia_models = []

        def solar_transport(payload, key, timeout):
            solar_models.append(payload["model"])
            schema = payload["response_format"]["json_schema"]["schema"]
            if "decisions" in schema["properties"]:
                content = json.loads(payload["messages"][1]["content"])
                return response({"decisions": {item["id"]: {
                    "field": "project_name", "role": "product_fact",
                    "status": "confirmed", "scope": "current", "decision": "selected"}
                    for item in content["candidates"]}})
            return response({"checkedFields": list(FIELDS), "issues": []})

        def nvidia_transport(payload, key, timeout):
            nvidia_models.append(payload["model"])
            content = json.dumps({"units": {"U0001": ["Alpha"]}})
            return json.dumps({"model": payload["model"], "choices": [
                {"finish_reason": "stop", "message": {"content": content}}],
                "usage": {}}).encode()

        analyzer = AnchoredAnalyzer(
            "solar-key", transport=solar_transport, prompt_revision="v2",
            candidate_occurrences=True, keyed_candidates=True,
            candidate_model="deepseek-ai/deepseek-v4.1-flash",
            candidate_api_key="nvidia-key", candidate_transport=nvidia_transport)
        result = analyzer.analyze("Alpha", "doc")
        self.assertEqual(result.profile["data"]["project_name"], "Alpha")
        self.assertEqual(solar_models, ["solar-pro4", "solar-pro4"])
        self.assertEqual(nvidia_models, ["deepseek-ai/deepseek-v4.1-flash"])
        self.assertEqual(result.diagnostics["calls"][0]["model"],
                         "deepseek-ai/deepseek-v4.1-flash")
        self.assertEqual(result.provider_calls, 3)

    def test_candidate_model_requires_valid_pair(self):
        for kwargs in ({"candidate_model": "unknown", "candidate_api_key": "key"},
                       {"candidate_model": "moonshotai/kimi-k3"},
                       {"candidate_api_key": "key"},
                       {"candidate_transport": Mock()}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                AnchoredAnalyzer("solar-key", **kwargs)

    def test_candidate_key_in_document_is_rejected_before_network(self):
        solar = Mock()
        nvidia = Mock()
        analyzer = AnchoredAnalyzer(
            "solar-key", transport=solar,
            candidate_model="deepseek-ai/deepseek-v4.1-flash",
            candidate_api_key="private-nvidia-token", candidate_transport=nvidia)
        with self.assertRaises(AnalysisError) as caught:
            analyzer.analyze("private-nvidia-token", "doc")
        self.assertEqual(caught.exception.code, "SENSITIVE_CONTENT")
        solar.assert_not_called()
        nvidia.assert_not_called()


if __name__ == "__main__":
    unittest.main()
