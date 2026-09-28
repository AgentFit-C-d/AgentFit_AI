import unittest
from unittest.mock import Mock

from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from agentfit_ai.solar import AnalysisError
from test_semantic_review import verdict, issue
from test_staged_analysis import response


class ObservedAnalyzer(AnchoredAnalyzer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []

    def _observe_judgment_failure(self, reply, pool, document, document_id, error):
        self.events.append(("judgment_failure", reply, pool, document, document_id, error.code))

    def _observe_profile(self, stage, profile):
        self.events.append(("profile", stage, profile))

    def _observe_review_issues(self, stage, issues):
        self.events.append(("issues", stage, issues))


class CheckpointTests(unittest.TestCase):
    def test_judgment_failure_hook_sees_reply_before_original_error(self):
        judgment = {"decisions": {"F0001": {"field": "project_name", "role": "product_fact",
                                           "status": "tentative", "scope": "current",
                                           "decision": "selected"}}}
        transport = Mock(side_effect=[response({"units": [{"unitId": "U0001", "quotes": ["Alpha"]}]}),
                                      response(judgment)])
        analyzer = ObservedAnalyzer("synthetic-key", transport=transport)
        with self.assertRaises(AnalysisError) as caught:
            analyzer.analyze("Alpha", "doc")
        self.assertEqual(caught.exception.code, "SECTION_MERGE")
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(len(analyzer.events), 1)
        event = analyzer.events[0]
        self.assertEqual(event[0], "judgment_failure")
        self.assertEqual(event[1], judgment)
        self.assertEqual(event[2][0]["quote"], "Alpha")
        self.assertEqual(event[3:], ("Alpha", "doc", "SECTION_MERGE"))

    def test_profile_and_review_hooks_follow_validation_order(self):
        first = {"F0001": {"field": "project_name", "role": "product_fact", "status": "confirmed",
                           "scope": "current", "decision": "selected"},
                 "F0002": {"field": "features", "role": "user_action", "status": "confirmed",
                           "scope": "current", "decision": "selected"}}
        repaired = {**first, "F0002": {**first["F0002"], "decision": "wrong_role"}}
        replies = [
            {"units": [{"unitId": "U0001", "quotes": ["Alpha", "checkout"]}]},
            {"decisions": first}, verdict([issue()]), {"decisions": repaired}, verdict(),
        ]
        transport = Mock(side_effect=[response(item) for item in replies])
        analyzer = ObservedAnalyzer("synthetic-key", transport=transport)
        result = analyzer.analyze("Alpha checkout", "doc")
        self.assertEqual(result.provider_calls, transport.call_count)
        self.assertEqual(result.provider_calls, 5)
        self.assertEqual([(event[0], event[1]) for event in analyzer.events],
                         [("profile", "judgment"), ("issues", "semantic_review"),
                          ("profile", "semantic_repair"), ("issues", "semantic_recheck")])
        self.assertEqual(analyzer.events[0][2]["data"]["features"], ["checkout"])
        self.assertIsNone(analyzer.events[2][2]["data"]["features"])
        self.assertEqual(analyzer.events[1][2][0]["field"], "features")
        self.assertEqual(analyzer.events[3][2], [])


if __name__ == "__main__":
    unittest.main()
