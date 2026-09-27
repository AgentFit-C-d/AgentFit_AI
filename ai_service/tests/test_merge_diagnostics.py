import unittest
from agentfit_ai.section_analysis import merge_profile
from agentfit_ai.solar import AnalysisError

class MergeDiagnosticTests(unittest.TestCase):
    def test_selection_errors_are_distinct_without_source_values(self):
        base={"id":"F0001","field":"features","value":"secret","quote":"secret",
              "span":{"start":0,"end":6},"role":"user_action","status":"confirmed","scope":"current"}
        for changes,reason in [
            ({"scope":"other"},"SELECTED_SCOPE"),
            ({"status":"tentative"},"SELECTED_STATUS"),
            ({"role":"development_task"},"SELECTED_ROLE")]:
            with self.subTest(reason=reason):
                with self.assertRaises(AnalysisError) as cm:
                    merge_profile("secret","doc",{"decisions":{"F0001":"selected"}},[{**base,**changes}])
                self.assertEqual(cm.exception.code,"SECTION_MERGE")
                self.assertEqual(getattr(cm.exception,"merge_detail",{}),{"reason":reason,"field":"features"})
                self.assertNotIn("secret",str(getattr(cm.exception,"merge_detail",{})))

    def test_duplicate_and_scalar_count_have_different_causes(self):
        base={"id":"F0001","field":"features","value":"x","span":{"start":0,"end":1},
              "role":"user_action","status":"confirmed","scope":"current"}
        for field,role,reason in (("features","user_action","DUPLICATE_VALUE"),("project_name","product_fact","SELECTED_COUNT")):
            pool=[{**base,"id":id,"field":field,"role":role} for id in ("F0001","F0002")]
            with self.assertRaises(AnalysisError) as cm:
                merge_profile("x","doc",{"decisions":{x["id"]:"selected" for x in pool}},pool)
            self.assertEqual(getattr(cm.exception,"merge_detail",{}).get("reason"),reason)
