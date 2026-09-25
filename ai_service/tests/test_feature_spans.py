import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError, cited_to_profile

class FeatureSpanTests(unittest.TestCase):
    def candidate(self, spans):
        fields=dict.fromkeys(FIELDS)
        fields["features"]={"spans":spans,"absenceLineIds":[]}
        return fields
    def test_feature_is_copied_from_source_not_generated_label(self):
        fields=self.candidate([{"lineId":1,"quote":"book search"}])
        r=cited_to_profile("Required: book search and loans.","doc-1",fields)
        self.assertEqual(r["data"]["features"],["book search"])
        self.assertEqual(r["evidence"]["features"],[{"documentId":"doc-1","start":10,"end":21}])
    def test_missing_reordered_or_ambiguous_quotes_rejected(self):
        for doc,span in [
            ("book search",{"lineId":1,"quote":"missing search"}),
            ("book search",{"lineId":1,"quote":"search book"}),
            ("book search; book search",{"lineId":1,"quote":"book search"})]:
            with self.subTest(doc=doc),self.assertRaises(AnalysisError) as caught:
                cited_to_profile(doc,"doc-1",self.candidate([span]))
            self.assertEqual(caught.exception.field,"features")
    def test_feature_count_limit_is_not_silently_truncated(self):
        spans=[{"lineId":1,"quote":"book search"}]*31
        with self.assertRaises(AnalysisError):
            cited_to_profile("book search","doc-1",self.candidate(spans))
    def test_span_and_absence_cannot_both_be_supplied(self):
        fields=self.candidate([{"lineId":1,"quote":"book search"}])
        fields["features"]["absenceLineIds"]=[1]
        with self.assertRaises(AnalysisError):
            cited_to_profile("book search","doc-1",fields)


    def test_whole_quote_disambiguates_repeated_boundary_words(self):
        fields=self.candidate([{"lineId":1,"quote":"book search"}])
        r=cited_to_profile("book search and book order","doc-1",fields)
        self.assertEqual(r["data"]["features"],["book search"])
