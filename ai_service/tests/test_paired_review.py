import unittest
from agentfit_ai.paired_review import assess_review

class PairedReviewTests(unittest.TestCase):
 def test_missing_issue_is_required_not_any_rejection(self):
  expected={"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}
  self.assertTrue(assess_review([expected],[expected])["matched"])
  self.assertFalse(assess_review([], [expected])["matched"])
  wrong={**expected,"field":"ai"}
  self.assertFalse(assess_review([wrong],[expected])["matched"])
  self.assertFalse(assess_review([expected,wrong],[expected])["matched"])

 def test_correct_profile_rejection_is_counted_separately(self):
  issue={"field":"features","kind":"overbroad","itemIndex":0,"evidenceLineIds":[1]}
  self.assertTrue(assess_review([],[])["matched"])
  result=assess_review([issue],[])
  self.assertFalse(result["matched"])
  self.assertTrue(result["false_rejection"])
  self.assertFalse(result["false_acceptance"])
  self.assertTrue(assess_review([], [issue])["false_acceptance"])

 def test_review_prompt_override_keeps_schema_and_effort(self):
  from unittest.mock import Mock
  from agentfit_ai.solar import SolarAnalyzer
  from test_staged_analysis import response
  from test_semantic_review import verdict
  t=Mock(return_value=response(verdict()))
  a=SolarAnalyzer("synthetic-key",transport=t)
  a._request_review("text",{"data":{},"evidence":{}},reasoning_effort="none",prompt="CUSTOM_REVIEW_CONTRACT")
  payload=t.call_args.args[0]
  self.assertEqual(payload["messages"][0]["content"],"CUSTOM_REVIEW_CONTRACT")
  self.assertEqual(payload["reasoning_effort"],"none")
  self.assertEqual(payload["response_format"]["json_schema"]["name"],"agentfit_semantic_review")

 def test_duplicate_evidence_ids_do_not_change_semantic_verdict(self):
  expected={"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}
  actual={**expected,"evidenceLineIds":[1,1]}
  result=assess_review([actual],[expected])
  self.assertTrue(result["matched"])
  self.assertFalse(result["exact_match"])

 def test_anchored_review_examples_do_not_change_extraction(self):
  from unittest.mock import Mock
  from agentfit_ai.anchored_analysis import AnchoredAnalyzer
  from test_staged_analysis import response
  from test_semantic_review import verdict
  t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),response(verdict())])
  result=AnchoredAnalyzer("synthetic-key",transport=t,review_examples=True).analyze("meeting","doc")
  self.assertIn("review-examples-v1",result.prompt_version)
  first,review=[c.args[0] for c in t.call_args_list]
  self.assertNotIn("북마크",first["messages"][0]["content"])
  self.assertIn("북마크",review["messages"][0]["content"])
