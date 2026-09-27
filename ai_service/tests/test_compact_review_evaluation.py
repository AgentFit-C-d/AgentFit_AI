import unittest

from agentfit_ai.compact_review_evaluation import review_metrics, aggregate


class CompactReviewEvaluationTests(unittest.TestCase):
    def test_review_metrics_split_timeout_and_invalid_reason(self):
        rows = [{"baseline": {"error": "PROVIDER_TIMEOUT", "calls": [
            {"stage": "semantic_review", "error": "PROVIDER_TIMEOUT"}]},
                 "compact": {"error": "SEMANTIC_REVIEW_INVALID", "calls": [
                     {"stage": "semantic_recheck", "error": "SEMANTIC_REVIEW_INVALID",
                      "review_error": {"reason": "ARRAY_INDEX"}}]}}]
        self.assertEqual(review_metrics(rows, "baseline")["timeouts"]["semantic_review"], 1)
        self.assertEqual(review_metrics(rows, "compact")["invalid_reasons"]["ARRAY_INDEX"], 1)

    def test_false_confirmation_blocks_promotion(self):
        rows = []
        for index in range(20):
            kind = "full" if index < 12 else "focus"
            total = 10 if kind == "full" else 3
            outcome = {"passed": True, "matched": total, "total": total,
                       "false_confirmations": 0, "provider_calls": 3,
                       "elapsed_ms": 1000, "calls": []}
            rows.append({"id": str(index), "kind": kind, "gold_total": total,
                         "baseline": outcome, "compact": dict(outcome)})
        rows[0]["compact"]["false_confirmations"] = 1
        self.assertFalse(aggregate(rows)["gate"]["false_confirmations_no_increase"])

    def test_full_complete_regression_cannot_hide_behind_equal_field_total(self):
        rows = []
        for index in range(20):
            kind = "full" if index < 12 else "focus"
            total = 10 if kind == "full" else 3
            baseline = {"passed": index == 0, "matched": 10 if index == 0 else 0,
                        "total": total, "false_confirmations": 0,
                        "provider_calls": 3, "elapsed_ms": 1000, "calls": []}
            compact = {**baseline, "passed": False,
                       "matched": 5 if index in (0, 1) else 0}
            rows.append({"id": str(index), "kind": kind, "gold_total": total,
                         "baseline": baseline, "compact": compact})
        gate = aggregate(rows)["gate"]
        self.assertTrue(gate["full_accuracy_no_regression"])
        self.assertFalse(gate["full_complete_no_regression"])
