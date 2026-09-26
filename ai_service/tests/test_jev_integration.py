import json
import unittest
from unittest.mock import Mock
from agentfit_ai.section_analysis import SectionAnalyzer
from agentfit_ai.solar import AnalysisError
from test_section_analysis import fact,extraction
from test_staged_analysis import response
from test_semantic_review import verdict,issue

def jev_response(choice="selected", ids=("F0001",)):
    reasons=("selected","not_current","not_confirmed","wrong_role","duplicate","conflict")
    return json.dumps({"model":"solar-jev","answers":{fid:{"type":"choice","choice":choice,
        "probabilities":{r:float(r==choice) for r in reasons},"confidence":0.9} for fid in ids},
        "usage":{"input_tokens":100,"output_tokens":1}}).encode()

class JevIntegrationTests(unittest.TestCase):
    def analyzer(self,replies,j,**kw):
        t=Mock(side_effect=[response(x) for x in replies])
        try:
            a=SectionAnalyzer("synthetic-key",model="solar-mini4",jev_merge=True,jev_transport=j,transport=t,**kw)
        except TypeError:
            self.fail("Jev integration is missing")
        return a,t
    def test_merge_uses_jev_and_review_uses_mini(self):
        j=Mock(return_value=jev_response())
        a,t=self.analyzer([extraction("S0001",fact("project_name","Alpha")),verdict()],j)
        r=a.analyze("Alpha","doc")
        self.assertEqual(r.profile["data"]["project_name"],"Alpha")
        self.assertEqual(r.provider_calls,3)
        self.assertEqual(r.diagnostics["calls"][1]["model"],"solar-jev")
        self.assertEqual(j.call_args.args[0]["state"]["document"],"Alpha")
        self.assertEqual(set(j.call_args.args[0]["questions"]),{"F0001"})
        self.assertTrue(all(c.args[0]["model"]=="solar-mini4" for c in t.call_args_list))
    def test_unknown_answer_id_fails(self):
        a,t=self.analyzer([extraction("S0001",fact("project_name","Alpha"))],Mock(return_value=jev_response(ids=("F9999",))))
        with self.assertRaises(AnalysisError):a.analyze("Alpha","doc")
    def test_wrong_role_is_still_rejected(self):
        a,t=self.analyzer([extraction("S0001",fact("features","checkout","development_task"))],Mock(return_value=jev_response()))
        with self.assertRaises(AnalysisError) as c:a.analyze("checkout","doc")
        self.assertEqual(c.exception.code,"SECTION_MERGE")
    def test_repair_uses_jev_with_shared_call_budget(self):
        j=Mock(return_value=jev_response())
        a,t=self.analyzer([extraction("S0001",fact("features","checkout","user_action")),
                           verdict([issue("overbroad")]),verdict()],j)
        r=a.analyze("checkout","doc")
        self.assertEqual(r.provider_calls,5)
        self.assertEqual(j.call_count,2)
        self.assertIn("issues",j.call_args.args[0]["state"])
    def test_empty_pool_does_not_call_jev(self):
        j=Mock()
        a,t=self.analyzer([extraction("S0001"),verdict()],j)
        r=a.analyze("No information","doc")
        self.assertTrue(all(x is None for x in r.profile["data"].values()))
        j.assert_not_called()
    def test_late_jev_response_cannot_succeed(self):
        now=[0]
        def j(*args):
            now[0]=61
            return jev_response()
        a,t=self.analyzer([extraction("S0001",fact("project_name","Alpha"))],j,clock=lambda:now[0])
        with self.assertRaises(AnalysisError) as c:a.analyze("Alpha","doc")
        self.assertEqual(c.exception.code,"ANALYSIS_DEADLINE")

    def test_huge_probability_is_a_controlled_failure(self):
        envelope=json.loads(jev_response())
        envelope["answers"]["F0001"]["probabilities"]["selected"]=10**400
        a,t=self.analyzer([extraction("S0001",fact("project_name","Alpha"))],
                          Mock(return_value=json.dumps(envelope).encode()))
        with self.assertRaises(AnalysisError) as c:a.analyze("Alpha","doc")
        self.assertEqual(c.exception.code,"SECTION_MERGE")
        self.assertEqual(c.exception.diagnostics["calls"][-1]["outcome"],"failed")
