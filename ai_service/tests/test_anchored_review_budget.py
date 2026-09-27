import unittest
from unittest.mock import Mock
from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from agentfit_ai import anchored_evaluation
from agentfit_ai.solar import AnalysisError
from test_staged_analysis import response
from test_semantic_review import verdict

class ReviewBudgetTests(unittest.TestCase):
    def test_review_option_does_not_change_extraction_or_judgment(self):
        replies=[{"units":[{"unitId":"U0001","quotes":["Alpha"]}]},
                 {"decisions":{"F0001":{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}}},
                 verdict()]
        for effort in ("medium","low"):
            with self.subTest(effort=effort):
                t=Mock(side_effect=[response(x) for x in replies])
                result=AnchoredAnalyzer("synthetic-key",transport=t,review_effort=effort).analyze("Alpha","doc")
                payloads=[c.args[0] for c in t.call_args_list]
                self.assertEqual([p["reasoning_effort"] for p in payloads],["none","none",effort])
                self.assertEqual([p["max_tokens"] for p in payloads],[4096,4096,8192])
                self.assertEqual(result.profile["data"]["project_name"],"Alpha")

    def test_failure_and_success_metadata_never_copy_source_text(self):
        diag={"elapsed_ms":59000,"calls":[{"stage":"semantic_review","outcome":"failed",
              "error":"PROVIDER_TIMEOUT","elapsed_ms":55000,"provider_elapsed_ms":54999,
              "completion_tokens":None,"prompt_tokens":None,"reasoning_effort":"low",
              "max_tokens":8192,"raw":"private source","semantic_issues":[{"field":"ai","kind":"missing","quote":"secret"}]}]}
        result=anchored_evaluation.safe_diagnostics(diag)
        self.assertEqual(result["elapsed_ms"],59000)
        self.assertEqual(result["calls"][0]["provider_elapsed_ms"],54999)
        self.assertEqual(result["calls"][0]["completion_tokens"],None)
        self.assertNotIn("private source",str(result))
        self.assertNotIn("secret",str(result))
        self.assertEqual(result["calls"][0]["semantic_issues"],[{"field":"ai","kind":"missing"}])
