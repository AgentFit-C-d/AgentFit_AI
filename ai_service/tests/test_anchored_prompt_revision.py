import unittest
from unittest.mock import Mock
from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from test_staged_analysis import response
from test_semantic_review import verdict

class PromptRevisionTests(unittest.TestCase):
 def test_opt_in_revision_is_recorded_and_produces_valid_profile(self):
  replies=[{"units":[{"unitId":"U0001","quotes":["Alpha"]}]},
           {"decisions":{"F0001":{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}}},
           verdict()]
  t=Mock(side_effect=[response(x) for x in replies])
  result=AnchoredAnalyzer("synthetic-key",transport=t,prompt_revision="v2").analyze("Alpha","doc")
  self.assertEqual(result.prompt_version,"anchored-v2")
  self.assertEqual(result.diagnostics["prompt_version"],"anchored-v2")
  self.assertEqual(result.profile["data"]["project_name"],"Alpha")
  self.assertEqual(result.provider_calls,3)
 def test_unknown_revision_rejected_before_network(self):
  with self.assertRaises(ValueError):
   AnchoredAnalyzer("synthetic-key",prompt_revision="unknown")
