import unittest
from unittest.mock import Mock

from agentfit_ai.solar import AnalysisResult, SolarAnalyzer
from agentfit_ai.analysis_timeout_evaluation import ReviewCappedAnchoredAnalyzer, failure_stage, aggregate


class TimeoutOptionTests(unittest.TestCase):
    def test_experimental_deadline_does_not_change_default_limits(self):
        baseline = SolarAnalyzer("synthetic-key")
        self.assertEqual((baseline._analysis_timeout_seconds,
                          baseline._field_call_timeout_seconds), (60, 40))
        with self.assertRaises(ValueError):
            SolarAnalyzer("synthetic-key", analysis_timeout_seconds=300)
        with self.assertRaises(ValueError):
            SolarAnalyzer("synthetic-key", field_call_timeout_seconds=120)
        trial = SolarAnalyzer("synthetic-key", analysis_timeout_seconds=300,
                              field_call_timeout_seconds=120,
                              experimental_long_timeout=True)
        self.assertEqual((trial._analysis_timeout_seconds,
                          trial._field_call_timeout_seconds), (300, 120))

    def test_experimental_review_token_limit_is_explicit(self):
        baseline = SolarAnalyzer("synthetic-key")
        self.assertEqual(baseline._review_max_tokens, 8192)
        with self.assertRaises(ValueError):
            SolarAnalyzer("synthetic-key", review_max_tokens=16384)
        analyzer = SolarAnalyzer("synthetic-key", experimental_long_timeout=True,
                                 review_max_tokens=16384)
        analyzer._send_payload = Mock(return_value=({}, "solar-pro4", 0, 0))
        profile = {"data": {field: None for field in (
            "project_name", "project_type", "domain", "frontend", "backend", "ai",
            "database", "deployment", "features", "external_integrations")},
                   "evidence": {field: [] for field in (
            "project_name", "project_type", "domain", "frontend", "backend", "ai",
            "database", "deployment", "features", "external_integrations")}}
        analyzer._request_review("document", profile)
        self.assertEqual(analyzer._send_payload.call_args.args[0]["max_tokens"], 16384)

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
