import unittest
from unittest.mock import Mock

from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from agentfit_ai.solar import AnalysisError
from test_staged_analysis import response
from test_semantic_review import verdict

try:
    from agentfit_ai.judgment_subspans import SUBSPAN_PROMPT, classify_subspans, subspan_schema
except ImportError:
    SUBSPAN_PROMPT = classify_subspans = subspan_schema = None


def selected(quote, field, role):
    return {"quote": quote, "field": field, "role": role,
            "status": "confirmed", "scope": "current", "decision": "selected"}


class JudgmentSubspanTests(unittest.TestCase):
    def test_full_analyzer_selects_two_facts_from_one_broad_candidate(self):
        document = "장소 확인과 후보 선택"
        transport = Mock(side_effect=[response(item) for item in (
            {"units": {"U0001": [document]}},
            {"decisions": {"F0001": {"facts": [
                selected("장소 확인", "features", "user_action"),
                selected("후보 선택", "features", "user_action")]}}},
            verdict(),
        )])
        analyzer = AnchoredAnalyzer(
            "synthetic-key", transport=transport, prompt_revision="v2",
            candidate_occurrences=True, keyed_candidates=True,
            judgment_subspans=True)
        result = analyzer.analyze(document, "doc")
        self.assertEqual(result.profile["data"]["features"],
                         ["장소 확인", "후보 선택"])
        self.assertEqual(result.provider_calls, 3)

    def test_two_actions_from_one_candidate_have_independent_evidence(self):
        self.assertIsNotNone(classify_subspans)
        document = "장소 확인과 후보 선택"
        pool = [{"id": "F0001", "unitId": "U0001", "quote": document,
                 "span": {"start": 0, "end": len(document)}}]
        reply = {"decisions": {"F0001": {"facts": [
            selected("장소 확인", "features", "user_action"),
            selected("후보 선택", "features", "user_action")]}}}
        profile = classify_subspans(reply, pool, document, "doc")
        self.assertEqual(profile["data"]["features"], ["장소 확인", "후보 선택"])
        self.assertEqual(profile["evidence"]["features"],
                         [{"documentId": "doc", "start": 0, "end": 5},
                          {"documentId": "doc", "start": 7, "end": 12}])

    def test_model_name_is_extracted_from_sentence_candidate(self):
        document = "서비스 운영 모델로 Lyra를 확정했다."
        pool = [{"id": "F0001", "unitId": "U0001", "quote": document,
                 "span": {"start": 0, "end": len(document)}}]
        reply = {"decisions": {"F0001": {"facts": [
            selected("Lyra", "ai", "operating_model")]}}}
        profile = classify_subspans(reply, pool, document, "doc")
        self.assertEqual(profile["data"]["ai"], ["Lyra"])
        self.assertEqual(profile["evidence"]["ai"],
                         [{"documentId": "doc", "start": 11, "end": 15}])

    def test_rejects_outside_ambiguous_overlap_and_partial_responses(self):
        document = "장소 확인과 후보 선택"
        pool = [{"id": "F0001", "unitId": "U0001", "quote": document,
                 "span": {"start": 0, "end": len(document)}}]
        good = selected("장소 확인", "features", "user_action")
        bad_replies = [
            {"decisions": {"F0001": {"facts": [selected("없는 값", "features", "user_action")]}}},
            {"decisions": {"F0001": {"facts": [good, selected("확인", "features", "user_action")]}}},
            {"decisions": {"F0001": {"facts": [dict(good, extra="x")]}}},
            {"decisions": {}},
        ]
        for reply in bad_replies:
            with self.subTest(reply=reply), self.assertRaises(AnalysisError):
                classify_subspans(reply, pool, document, "doc")
        repeated = "반복 반복"
        repeated_pool = [{"id": "F0001", "unitId": "U0001", "quote": repeated,
                          "span": {"start": 0, "end": len(repeated)}}]
        with self.assertRaises(AnalysisError):
            classify_subspans({"decisions": {"F0001": {"facts": [
                selected("반복", "features", "user_action")]}}},
                repeated_pool, repeated, "doc")

    def test_schema_requires_all_candidate_ids_and_facts(self):
        self.assertIsNotNone(subspan_schema)
        pool = [{"id": "F0001"}, {"id": "F0002"}]
        schema = subspan_schema(pool)
        decisions = schema["properties"]["decisions"]
        self.assertEqual(set(decisions["required"]), {"F0001", "F0002"})
        self.assertEqual(decisions["properties"]["F0001"]["properties"]["facts"]["maxItems"], 5)
        branches = decisions["properties"]["F0001"]["properties"]["facts"]["items"]["anyOf"]
        for branch in branches:
            props = branch["properties"]
            if "selected" in props["decision"]["enum"]:
                self.assertEqual(props["decision"]["enum"], ["selected"])
                self.assertTrue(set(props["status"]["enum"]) <= {"confirmed", "absent"})
                self.assertEqual(props["scope"]["enum"], ["current"])
        self.assertIn('각 값은 {"facts":[]}', SUBSPAN_PROMPT)
        self.assertNotIn('후보 인용은 바꾸거나 추가할 수 없다', SUBSPAN_PROMPT)


if __name__ == "__main__":
    unittest.main()
