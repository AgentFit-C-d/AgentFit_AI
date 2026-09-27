import json
import unittest
from unittest.mock import Mock

from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.solar import AnalysisError
from test_staged_analysis import response


class CompactReviewPipelineTests(unittest.TestCase):
    def test_opt_in_review_keeps_profile_and_call_count(self):
        def transport(payload, key, timeout):
            schema = payload["response_format"]["json_schema"]["schema"]
            if schema["properties"].get("issues") is not None:
                self.assertEqual(set(schema["properties"]), {"issues"})
                self.assertEqual(payload["max_tokens"], 4096)
                return response({"issues": []})
            content = json.loads(payload["messages"][1]["content"])
            if "units" in content:
                return response({"units": {unit["unitId"]: ["Alpha"] for unit in content["units"]}})
            return response({"decisions": {candidate["id"]: {
                "field": "project_name", "role": "product_fact", "status": "confirmed",
                "scope": "current", "decision": "selected"} for candidate in content["candidates"]}})

        analyzer = AnchoredAnalyzer("synthetic-key", transport=Mock(side_effect=transport),
                                   prompt_revision="v2", candidate_occurrences=True,
                                   keyed_candidates=True, compact_review=True)
        result = analyzer.analyze("Alpha", "doc")
        self.assertEqual(result.profile["data"]["project_name"], "Alpha")
        self.assertEqual(result.provider_calls, 3)
        self.assertIn("compact-review", result.prompt_version)

    def test_invalid_target_id_fails_without_partial_profile(self):
        replies = [
            {"units": {"U0001": ["Alpha"]}},
            {"decisions": {"F0001": {"field": "project_name", "role": "product_fact",
                                      "status": "confirmed", "scope": "current", "decision": "selected"}}},
            {"issues": [{"field": "features", "kind": "wrong_role",
                         "targetId": "I9999", "sourceLineIds": []}]},
        ]
        analyzer = AnchoredAnalyzer("synthetic-key", transport=Mock(side_effect=[response(item) for item in replies]),
                                   prompt_revision="v2", candidate_occurrences=True,
                                   keyed_candidates=True, compact_review=True)
        with self.assertRaises(AnalysisError) as caught:
            analyzer.analyze("Alpha", "doc")
        self.assertEqual(caught.exception.code, "SEMANTIC_REVIEW_INVALID")
        self.assertEqual(caught.exception.diagnostics["calls"][-1]["review_error"]["reason"], "SCALAR_INDEX")

    def test_option_type_is_checked(self):
        with self.assertRaises(ValueError):
            AnchoredAnalyzer("synthetic-key", compact_review="yes")

    def test_long_valid_evidence_does_not_fail_before_provider(self):
        document = "X\n" * 31
        profile = validate_profile(document, "doc", {
            "data": {**dict.fromkeys(FIELDS), "project_name": "X"},
            "evidence": {**{field: [] for field in FIELDS},
                         "project_name": [{"start": 0, "end": len(document)}]},
        })
        transport = Mock(return_value=response({"issues": []}))
        analyzer = AnchoredAnalyzer("synthetic-key", compact_review=True,
                                   transport=transport)
        analyzer._request_review(document, profile)
        transport.assert_called_once()
