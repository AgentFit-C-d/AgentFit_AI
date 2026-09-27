import unittest
from unittest.mock import Mock

from agentfit_ai.solar import AnalysisResult, SolarAnalyzer
from agentfit_ai.analysis_timeout_evaluation import ReviewCappedAnchoredAnalyzer, failure_stage, aggregate


class TimeoutOptionTests(unittest.TestCase):
    def test_default_and_opt_in_deadlines(self):
        for seconds in (60, 120):
            with self.subTest(seconds=seconds):
                kwargs = {} if seconds == 60 else {"analysis_timeout_seconds": seconds}
                analyzer = SolarAnalyzer("synthetic-key", clock=lambda: 10, **kwargs)
                analyzer._analyze = Mock(return_value=AnalysisResult({}, "solar-pro4", None, None, 0))
                analyzer.analyze("text", "doc")
                self.assertEqual(analyzer._analyze.call_args.args[-1], 10 + seconds)

    def test_invalid_timeouts_rejected(self):
        for value in (True, 0, -1, 121, 60.5, "120"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SolarAnalyzer("synthetic-key", analysis_timeout_seconds=value)

    def test_review_cap_is_identical_for_both_arms(self):
        for seconds in (60, 120):
            analyzer = ReviewCappedAnchoredAnalyzer(
                "synthetic-key", prompt_revision="v2", candidate_occurrences=True,
                keyed_candidates=True, analysis_timeout_seconds=seconds)
            analyzer._request_review_uncapped = Mock(return_value=(None, "solar-pro4", 0, 0))
            analyzer._request_review("document", {}, timeout=seconds)
            self.assertEqual(analyzer._request_review_uncapped.call_args.kwargs["timeout"], 40)

    def test_timeout_stage_uses_failed_call_only(self):
        self.assertEqual(failure_stage({"calls": [
            {"stage": "candidate_generation", "outcome": "validated"},
            {"stage": "semantic_review", "outcome": "failed", "error": "PROVIDER_TIMEOUT"}]}, "PROVIDER_TIMEOUT"),
            "semantic_review")
        self.assertEqual(failure_stage({"calls": [
            {"stage": "semantic_review", "outcome": "semantic_failed"}]}, "ANALYSIS_DEADLINE"),
            "between_calls")
        self.assertIsNone(failure_stage({"calls": []}, "PROVIDER_FAILURE"))

    def test_accuracy_regression_blocks_success_gate(self):
        rows = []
        for i in range(20):
            kind = "full" if i < 12 else "focus"
            total = 10 if kind == "full" else 3
            sixty = {"passed": i == 0, "matched": total if i == 0 else 2,
                     "total": total, "false_confirmations": 0,
                     "provider_calls": 3, "elapsed_ms": 1000}
            longer = {**sixty, "passed": i in (0, 1), "matched": total if i in (0, 1) else 0}
            rows.append({"kind": kind, "gold_total": total,
                         "sixty": sixty, "one_twenty": longer})
        gate = aggregate(rows)["gate"]
        self.assertTrue(gate["successes_increase"])
        self.assertFalse(gate["full_accuracy_no_regression"])
