import unittest
from unittest.mock import Mock

from agentfit_ai.profile import FIELDS
from agentfit_ai.default_review_effort_comparison import (
    ReviewEffortSolarAnalyzer, run_pair, summarize,
)


class DefaultReviewEffortComparisonTests(unittest.TestCase):
    def test_only_review_payload_uses_low_effort(self):
        analyzer = ReviewEffortSolarAnalyzer("synthetic-key", review_effort="low")
        analyzer._send_payload = Mock(return_value=({}, "solar-pro4", 0, 0))
        profile = {"data": dict.fromkeys(FIELDS),
                   "evidence": {field: [] for field in FIELDS}}
        analyzer._request_fields("Alpha service", ("backend",), "extract")
        extraction = analyzer._send_payload.call_args.args[0]
        analyzer._request_review("Alpha service", profile)
        review = analyzer._send_payload.call_args.args[0]
        self.assertEqual(extraction["reasoning_effort"], "none")
        self.assertEqual(review["reasoning_effort"], "low")
        self.assertEqual(review["model"], extraction["model"])
        self.assertEqual(review["max_tokens"], 8192)

    def test_case_order_alternates_and_failures_stay_unscored(self):
        seen = []

        def run_arm(case, key, effort):
            seen.append(effort)
            return {"outcome": "failed" if effort == "low" else "complete",
                    "passed": effort == "medium", "matched": 1 if effort == "medium" else None,
                    "gold_total": 1, "false_confirmations": 0 if effort == "medium" else None,
                    "provider_calls": 3, "elapsed_ms": 10, "error": "PROVIDER_TIMEOUT" if effort == "low" else None,
                    "call_timings": []}

        case = {"id": "S-1", "kind": "full", "document": "private source"}
        first = run_pair(case, "private-key", 0, run_arm=run_arm)
        second = run_pair(case, "private-key", 1, run_arm=run_arm)
        self.assertEqual(seen, ["medium", "low", "low", "medium"])
        self.assertEqual(first["order"], ["medium", "low"])
        self.assertEqual(second["order"], ["low", "medium"])
        report = summarize([first])
        self.assertEqual(report["paired_complete_cases"], 0)
        self.assertEqual(report["arms"]["low"]["failed_cases"], 1)
        self.assertEqual(report["arms"]["low"]["wrong_auto_confirmations"], 0)

    def test_review_effort_rejects_unsupported_value(self):
        with self.assertRaises(ValueError):
            ReviewEffortSolarAnalyzer("synthetic-key", review_effort="none")


if __name__ == "__main__":
    unittest.main()
