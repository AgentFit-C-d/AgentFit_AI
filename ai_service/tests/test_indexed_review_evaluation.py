import unittest
from unittest.mock import Mock

from agentfit_ai.indexed_review_evaluation import IndexedReviewSolarAnalyzer, run_pair, summarize
from agentfit_ai.profile import FIELDS


class IndexedReviewEvaluationTests(unittest.TestCase):
    def test_only_indexed_arm_adds_guide(self):
        analyzer=IndexedReviewSolarAnalyzer("synthetic-key")
        analyzer._send_payload=Mock(return_value=({},"solar-pro4",0,0))
        profile={"data":dict.fromkeys(FIELDS),
                 "evidence":{field:[] for field in FIELDS}}
        profile["data"]["features"]=["예약 확인"]
        analyzer._request_review("예약 확인",profile)
        payload=analyzer._send_payload.call_args.args[0]
        self.assertIn('"itemIndex": 0',payload["messages"][1]["content"])
        self.assertEqual(payload["reasoning_effort"],"medium")

    def test_pair_order_and_invalid_reasons_are_counted_without_failure_masking(self):
        seen=[]
        def run_arm(case,key,arm):
            seen.append(arm)
            failed=arm=="indexed"
            return {"outcome":"failed" if failed else "complete", "passed":not failed,
                    "matched":None if failed else 1,"gold_total":1,
                    "false_confirmations":None if failed else 0,
                    "provider_calls":3,"elapsed_ms":10,
                    "error":"SEMANTIC_REVIEW_INVALID" if failed else None,
                    "call_timings":[{"stage":"semantic_review","outcome":"validation_failed",
                                     "elapsed_ms":10,"review_invalid_reason":"ARRAY_INDEX"}]
                    if failed else []}
        case={"id":"C1","kind":"full","document":"private source"}
        first=run_pair(case,"private-key",0,run_arm=run_arm)
        second=run_pair(case,"private-key",1,run_arm=run_arm)
        self.assertEqual(seen,["baseline","indexed","indexed","baseline"])
        self.assertEqual(first["order"],["baseline","indexed"])
        self.assertEqual(second["order"],["indexed","baseline"])
        summary=summarize([first])
        self.assertEqual(summary["arms"]["indexed"]["review_invalid_reasons"],
                         {"ARRAY_INDEX":1})
        self.assertEqual(summary["arms"]["indexed"]["failed_cases"],1)
        self.assertFalse(summary["screen_passed"])

    def test_array_error_replacement_by_timeout_is_not_an_improvement(self):
        def complete():
            return {"outcome":"complete","passed":True,"matched":1,"gold_total":1,
                    "false_confirmations":0,"provider_calls":3,"elapsed_ms":20,
                    "error":None,"call_timings":[]}
        def failed(error,reason=None):
            call={"stage":"semantic_review","outcome":"validation_failed","elapsed_ms":5}
            if reason:call["review_invalid_reason"]=reason
            return {"outcome":"failed","passed":False,"matched":None,"gold_total":1,
                    "false_confirmations":None,"provider_calls":3,"elapsed_ms":10,
                    "error":error,"call_timings":[call]}
        rows=[{"id":"C1","kind":"full","order":["baseline","indexed"],
               "baseline":failed("SEMANTIC_REVIEW_INVALID","ARRAY_INDEX"),
               "indexed":failed("PROVIDER_TIMEOUT")},
              {"id":"C2","kind":"full","order":["indexed","baseline"],
               "baseline":complete(),"indexed":complete()}]
        result=summarize(rows)
        self.assertEqual(result["arms"]["baseline"]["failed_cases"],1)
        self.assertEqual(result["arms"]["indexed"]["failed_cases"],1)
        self.assertFalse(result["screen_passed"])


if __name__=="__main__":
    unittest.main()
