import unittest
from agentfit_ai.repair_observation import score_profile,observe_run
from agentfit_ai.profile import FIELDS,validate_profile
from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from test_staged_analysis import response
from test_semantic_review import verdict
from unittest.mock import Mock
from test_source_repair import fact,reply

def profile(data):
 return {"data":dict.fromkeys(FIELDS)|data,"sources":{f:"DOCUMENT" if data.get(f) is not None else "UNKNOWN" for f in FIELDS}}

class ObservationTests(unittest.TestCase):
 def test_exact_gold_aliases_and_broad_coverage_are_distinct(self):
  result=score_profile(profile({"features":["search and reserve"]}),{"features":[["search"],["reserve"]]})
  self.assertFalse(result["passed"])
  self.assertEqual(result["mismatch_fields"],["features"])
  self.assertEqual(result["fields"]["features"]["covered_groups"],2)
  self.assertEqual(result["fields"]["features"]["exact_groups"],0)
  self.assertNotIn("search",str(result))

 def test_absence_unknown_and_scalar(self):
  self.assertTrue(score_profile(profile({"external_integrations":[]}),{"external_integrations":[]})["passed"])
  self.assertFalse(score_profile(profile({}),{"external_integrations":[]})["passed"])
  self.assertTrue(score_profile(profile({"project_name":"Alpha"}),{"project_name":"Alpha"})["passed"])
  self.assertFalse(score_profile(profile({"ai":["Alpha"]}),{})["passed"])

 def test_observer_distinguishes_correct_repair_rejected_by_review(self):
  missing={"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}
  overbroad={"field":"features","kind":"overbroad","itemIndex":0,"evidenceLineIds":[1]}
  t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
                     response(verdict([missing])),response(reply("features",[fact("search")])),
                     response(verdict([overbroad]))])
  analyzer=AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True)
  result=observe_run(analyzer,"search","doc",{"features":[["search","GOLD_ONLY_MARKER"]]})
  self.assertFalse(result["passed"])
  self.assertEqual(result["error"],"SEMANTIC_REJECTED")
  self.assertTrue(result["repairs"][0]["passed"])
  self.assertTrue(result["review_inputs"][1]["passed"])
  self.assertNotIn("GOLD_ONLY_MARKER",str(t.call_args_list))
  self.assertNotIn("search",str(result))
  self.assertEqual(len(result["calls"]),4)

 def test_one_value_cannot_satisfy_two_gold_groups(self):
  result=score_profile(profile({"features":["search"]}),{"features":[["search","reserve"],["search"]]})
  self.assertFalse(result["passed"])
  self.assertEqual(result["fields"]["features"]["exact_groups"],1)
