import json
import unittest
from unittest.mock import Mock

from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.solar import AnalysisError
from test_staged_analysis import response


class ReviewModelRoutingTests(unittest.TestCase):
    def test_compact_review_uses_nvidia_only_for_review(self):
        solar_models = []
        nvidia_models = []
        def solar_transport(payload, key, timeout):
            solar_models.append(payload["model"])
            content = json.loads(payload["messages"][1]["content"])
            if "units" in content:
                return response({"units": {unit["unitId"]: ["Alpha"] for unit in content["units"]}})
            return response({"decisions": {candidate["id"]: {
                "field": "project_name", "role": "product_fact", "status": "confirmed",
                "scope": "current", "decision": "selected"} for candidate in content["candidates"]}})
        def nvidia_transport(payload, key, timeout):
            nvidia_models.append(payload["model"])
            return json.dumps({"model": payload["model"], "choices": [{"finish_reason": "stop",
                "message": {"content": '{"issues":[]}'}}], "usage": {}}).encode()

        model = "deepseek-ai/deepseek-v4.1-flash"
        analyzer = AnchoredAnalyzer("solar-key", transport=solar_transport,
            review_model=model, review_api_key="nvidia-key", compact_review=True,
            prompt_revision="v2", candidate_occurrences=True, keyed_candidates=True)
        analyzer._nvidia_reviewer._solar_parser._transport = nvidia_transport
        result = analyzer.analyze("Alpha", "doc")
        self.assertEqual(result.profile["data"]["project_name"], "Alpha")
        self.assertEqual(solar_models, ["solar-pro4", "solar-pro4"])
        self.assertEqual(nvidia_models, [model])
        self.assertEqual(result.diagnostics["calls"][-1]["model"], model)

    def test_standard_review_uses_nvidia_sender_and_keeps_schema(self):
        document = "Alpha"
        profile = validate_profile(document, "doc", {
            "data": {**dict.fromkeys(FIELDS), "project_name": "Alpha"},
            "evidence": {**{field: [] for field in FIELDS},
                         "project_name": [{"start": 0, "end": 5}]},
        })
        seen = []
        def nvidia_transport(payload, key, timeout):
            seen.append(payload)
            content = json.dumps({"checkedFields": list(FIELDS), "issues": []})
            return json.dumps({"model": payload["model"], "choices": [{"finish_reason": "stop",
                "message": {"content": content}}], "usage": {}}).encode()
        analyzer = AnchoredAnalyzer("solar-key", review_model="z-ai/glm-5.3",
                                    review_api_key="nvidia-key")
        analyzer._nvidia_reviewer._solar_parser._transport = nvidia_transport
        reply = analyzer._request_review(document, profile)
        self.assertEqual(reply[1], "z-ai/glm-5.3")
        self.assertEqual(set(seen[0]["response_format"]["json_schema"]["schema"]["properties"]),
                         {"checkedFields", "issues"})
        self.assertEqual(seen[0]["reasoning_effort"], "low")

    def test_model_and_key_are_validated_before_call(self):
        for kwargs in ({"review_model": "unknown/model", "review_api_key": "key"},
                       {"review_model": "moonshotai/kimi-k3"},
                       {"review_api_key": "key"}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                AnchoredAnalyzer("solar-key", **kwargs)

    def test_nvidia_key_in_document_is_rejected_before_solar_call(self):
        solar = Mock()
        analyzer = AnchoredAnalyzer("solar-key", transport=solar,
            review_model="deepseek-ai/deepseek-v4.1-flash",
            review_api_key="private-nvidia-token")
        with self.assertRaises(AnalysisError) as caught:
            analyzer.analyze("private-nvidia-token", "doc")
        self.assertEqual(caught.exception.code, "SENSITIVE_CONTENT")
        solar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
