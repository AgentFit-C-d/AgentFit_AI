import json
import unittest
from unittest.mock import Mock
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import SolarAnalyzer, AnalysisError, safe_evidence_failure
from test_staged_analysis import response
from test_evidence_contract import fact, confirmed
from test_semantic_review import verdict, issue

def core():
    return dict({f:None for f in FIELDS if f!="features"}, project_name=confirmed(fact("Alpha")))
def features(*names):
    return {"features":confirmed(*(fact(n,role="user_action") for n in names))}

class EvidencePipelineTests(unittest.TestCase):
    def run_replies(self,replies):
        t=Mock(side_effect=[response(x) for x in replies])
        return SolarAnalyzer("synthetic-key",transport=t),t
    def test_default_contract_and_public_profile(self):
        a,t=self.run_replies([core(),features("checkout"),verdict()])
        r=a.analyze("Alpha checkout","doc")
        self.assertEqual(r.profile["data"]["features"],["checkout"])
        self.assertTrue(r.semantic_reviewed)
        self.assertEqual(r.provider_calls,3)
        self.assertEqual(r.diagnostics["evidence_contract"],"evidence-v1")
        schema=t.call_args_list[1].args[0]["response_format"]["json_schema"]["schema"]
        self.assertNotIn("occurrence",json.dumps(schema))
        self.assertNotIn("lineId",json.dumps(schema))
    def test_duplicate_repair_has_common_index_and_reason(self):
        a,t=self.run_replies([core(),features("checkout","checkout"),features("checkout"),verdict()])
        r=a.analyze("Alpha checkout","doc")
        self.assertEqual(r.provider_calls,4)
        correction=t.call_args_list[2].args[0]["messages"][1]["content"].split("Correction data (not document text):\n")[1]
        self.assertEqual(json.loads(correction)["errors"][0]["detail"],{"reason":"DUPLICATE_VALUE","itemIndex":1})
        self.assertFalse(r.first_pass_validated)
    def test_old_shape_never_silently_falls_back(self):
        a,t=self.run_replies([core(),{"features":{"spans":[],"absenceLineIds":[1]}},{"features":{"spans":[],"absenceLineIds":[1]}}])
        with self.assertRaises(AnalysisError) as caught:a.analyze("Alpha checkout","doc")
        self.assertEqual(caught.exception.code,"INVALID_EVIDENCE")
        self.assertEqual(t.call_count,3)
    def test_final_repair_failure_records_field_and_reason_without_source(self):
        bad = features("private-marker")
        a,_ = self.run_replies([core(),bad,bad])
        with self.assertRaises(AnalysisError) as caught:
            a.analyze("Alpha checkout","doc")
        call = caught.exception.diagnostics["calls"][-1]
        self.assertEqual(call["stage"],"repair")
        self.assertEqual(call["validation_error"],
                         {"field":"features","reason":"QUOTE_NOT_FOUND","itemIndex":0,
                          "matchCount":0})
        self.assertNotIn("private-marker",json.dumps(call))
    def test_arbitrary_projection_detail_is_not_exposed(self):
        error = AnalysisError("INVALID_EVIDENCE","features")
        error.detail = {"reason":"PRIVATE_SOURCE_TEXT","itemIndex":0}
        self.assertIsNone(safe_evidence_failure(error))
        error.detail = {"reason":["PRIVATE_SOURCE_TEXT"]}
        self.assertIsNone(safe_evidence_failure(error))
        error.detail = {"reason":"QUOTE_NOT_FOUND","itemIndex":0,
                        "matchCount":0,"private":"source text"}
        self.assertEqual(safe_evidence_failure(error),
                         {"field":"features","reason":"QUOTE_NOT_FOUND",
                          "itemIndex":0,"matchCount":0})
    def test_semantic_repair_projection_failure_records_same_safe_detail(self):
        a,_ = self.run_replies([core(),features("checkout"),
                                verdict([issue("overbroad")]),features("private-marker")])
        with self.assertRaises(AnalysisError) as caught:
            a.analyze("Alpha checkout","doc")
        call = caught.exception.diagnostics["calls"][-1]
        self.assertEqual(call["stage"],"semantic_repair")
        self.assertEqual(call["validation_error"],
                         {"field":"features","reason":"QUOTE_NOT_FOUND",
                          "itemIndex":0,"matchCount":0})
    def test_structural_then_semantic_repair_remains_six_calls(self):
        a,t=self.run_replies([core(),features("missing"),features("checkout"),verdict([issue("overbroad")]),features("checkout"),verdict()])
        r=a.analyze("Alpha checkout","doc")
        self.assertEqual(r.provider_calls,6)
        self.assertEqual(r.repaired_fields,("features",))

    def test_short_quote_cannot_hide_pending_model_decision(self):
        fields=dict.fromkeys(FIELDS)
        fields["ai"]=confirmed(fact("Lumen",role="operating_model"))
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key")._project("Lumen을 먼저 평가하고 운영 채택은 품질 검증 후 결정한다.","doc",fields)
        self.assertEqual(caught.exception.code,"UNCONFIRMED_PROFILE_VALUE")

    def test_other_line_pending_model_does_not_override_confirmed_occurrence(self):
        fields=dict.fromkeys(FIELDS)
        fields["ai"]=confirmed(fact("Lumen",context="운영 모델은 Lumen으로 확정한다.",role="operating_model"))
        doc="과거에는 Lumen을 먼저 평가하고 운영 채택은 품질 검증 후 결정한다.\n운영 모델은 Lumen으로 확정한다."
        p=SolarAnalyzer("synthetic-key")._project(doc,"doc",fields)
        self.assertEqual(p["data"]["ai"],["Lumen"])
