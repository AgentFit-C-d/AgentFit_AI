import unittest
from unittest.mock import Mock

from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from test_recoverable_analysis import candidates, chosen
from test_semantic_review import issue, verdict
from test_staged_analysis import response

try:
    from agentfit_ai.false_complete_observation import ObservedRecoverableAnalyzer
except ImportError:
    ObservedRecoverableAnalyzer = None


class CandidateHookAnalyzer(AnchoredAnalyzer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate_pools = []

    def _observe_candidate_pool(self, pool):
        self.candidate_pools.append(pool)


class FalseCompleteObservationTests(unittest.TestCase):
    def test_candidate_hook_runs_once_before_judgment(self):
        transport = Mock(side_effect=[
            response(candidates("Alpha")),
            response({"decisions": {"F0001": chosen("project_name")}}),
            response(verdict()),
        ])
        analyzer = CandidateHookAnalyzer("synthetic-key", transport=transport)
        result = analyzer.analyze("Alpha", "doc")
        self.assertEqual(result.profile["data"]["project_name"], "Alpha")
        self.assertEqual(len(analyzer.candidate_pools), 1)
        self.assertEqual(analyzer.candidate_pools[0][0]["id"], "F0001")
        self.assertEqual(transport.call_count, 3)

    def test_observed_result_equals_recoverable_result(self):
        self.assertIsNotNone(ObservedRecoverableAnalyzer)
        replies = [candidates("Alpha"),
                   {"decisions": {"F0001": chosen("project_name")}}, verdict()]
        transport = Mock(side_effect=[response(item) for item in replies])
        analyzer = ObservedRecoverableAnalyzer("synthetic-key", transport=transport)
        result, observation = analyzer.analyze_observed("Alpha", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(transport.call_count, 3)
        self.assertEqual(observation["candidates"], [{"id": "F0001", "start": 0, "end": 5}])
        self.assertEqual([stage for stage, _ in observation["profiles"]], ["judgment"])
        self.assertEqual([stage for stage, _ in observation["reviews"]], ["semantic_review"])
        self.assertNotIn("quote", observation["candidates"][0])

    def test_review_and_recheck_stages_are_distinct(self):
        self.assertIsNotNone(ObservedRecoverableAnalyzer)
        first = {"F0001": chosen("project_name"),
                 "F0002": chosen("features", "user_action")}
        repaired = {**first, "F0002": chosen("features", "user_action", decision="wrong_role")}
        replies = [candidates("Alpha", "checkout"), {"decisions": first},
                   verdict([issue("overbroad")]), {"decisions": repaired}, verdict()]
        transport = Mock(side_effect=[response(item) for item in replies])
        analyzer = ObservedRecoverableAnalyzer("synthetic-key", transport=transport)
        result, observation = analyzer.analyze_observed("Alpha checkout", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 5)
        self.assertEqual([stage for stage, _ in observation["profiles"]],
                         ["judgment", "semantic_repair"])
        self.assertEqual([stage for stage, _ in observation["reviews"]],
                         ["semantic_review", "semantic_recheck"])
        self.assertEqual(observation["reviews"][0][1][0]["field"], "features")
        self.assertEqual(observation["reviews"][1][1], [])

    def test_context_resets_after_error_and_isolates_calls(self):
        self.assertIsNotNone(ObservedRecoverableAnalyzer)
        replies = [candidates("missing"), candidates("Alpha"),
                   {"decisions": {"F0001": chosen("project_name")}}, verdict()]
        transport = Mock(side_effect=[response(item) for item in replies])
        analyzer = ObservedRecoverableAnalyzer("synthetic-key", transport=transport)
        failed, first = analyzer.analyze_observed("Alpha", "first")
        complete, second = analyzer.analyze_observed("Alpha", "second")
        self.assertEqual(failed["outcome"], "failed")
        self.assertEqual(first["candidates"], [])
        self.assertEqual(first["profiles"], [])
        self.assertEqual(complete["outcome"], "complete")
        self.assertEqual(len(second["candidates"]), 1)
        self.assertEqual(len(second["profiles"]), 1)
        self.assertEqual(transport.call_count, 4)

    def test_judgment_merge_failure_records_only_fixed_reason(self):
        decisions = {"F0001": chosen("project_name"),
                     "F0002": chosen("project_name")}
        transport = Mock(side_effect=[response(item) for item in (
            candidates("Alpha", "Beta"), {"decisions": decisions})])
        analyzer = ObservedRecoverableAnalyzer("synthetic-key", transport=transport)
        result, observation = analyzer.analyze_observed("Alpha Beta", "doc")
        self.assertNotEqual(result["outcome"], "complete")
        self.assertEqual(observation["judgment_failure_reason"], "SELECTED_COUNT")
        self.assertNotIn("Alpha", str(observation["judgment_failure_reason"]))


if __name__ == "__main__":
    unittest.main()
