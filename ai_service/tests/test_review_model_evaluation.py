import unittest

from agentfit_ai.review_model_evaluation import safe_model_diagnostics


class ReviewModelEvaluationTests(unittest.TestCase):
    def test_safe_diagnostics_keeps_allowlisted_model_only(self):
        result = safe_model_diagnostics({"calls": [
            {"call": 1, "stage": "judgment", "model": "solar-pro4"},
            {"call": 2, "stage": "semantic_review",
             "model": "deepseek-ai/deepseek-v4.1-flash"},
            {"call": 3, "stage": "semantic_recheck", "model": "secret or provider text"},
        ]})
        self.assertEqual([call.get("model") for call in result["calls"]],
                         ["solar-pro4", "deepseek-ai/deepseek-v4.1-flash", None])


if __name__ == "__main__":
    unittest.main()
