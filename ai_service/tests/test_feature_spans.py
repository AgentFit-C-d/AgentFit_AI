import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError, cited_to_profile

class FeatureSpanTests(unittest.TestCase):
    def candidate(self, spans):
        fields=dict.fromkeys(FIELDS)
        fields["features"]={"spans":spans,"absenceLineIds":[]}
        return fields
    def span(self,start=1,end=2):
        return {"lineId":1,"startId":start,"endId":end,"role":"user_action"}
    def test_feature_is_copied_from_source_not_generated_label(self):
        fields=self.candidate([self.span(3,4)])
        r=cited_to_profile("Required: book search and loans.","doc-1",fields)
        self.assertEqual(r["data"]["features"],["book search"])
        self.assertEqual(r["evidence"]["features"],[{"documentId":"doc-1","start":10,"end":21}])
    def test_missing_reordered_or_out_of_range_ids_rejected(self):
        for span in [self.span(0,2),self.span(2,1),self.span(1,3)]:
            with self.subTest(span=span),self.assertRaises(AnalysisError) as caught:
                cited_to_profile("book search","doc-1",self.candidate([span]))
            self.assertEqual(caught.exception.field,"features")
    def test_feature_count_limit_is_not_silently_truncated(self):
        with self.assertRaises(AnalysisError):
            cited_to_profile("book search","doc-1",self.candidate([self.span()]*31))
    def test_span_and_absence_cannot_both_be_supplied(self):
        fields=self.candidate([self.span()])
        fields["features"]["absenceLineIds"]=[1]
        with self.assertRaises(AnalysisError):
            cited_to_profile("book search","doc-1",fields)
    def test_ids_disambiguate_repeated_boundary_words(self):
        r=cited_to_profile("book search and book order","doc-1",self.candidate([self.span(4,5)]))
        self.assertEqual(r["data"]["features"],["book order"])
