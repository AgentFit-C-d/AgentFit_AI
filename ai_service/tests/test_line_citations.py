import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError, cited_to_profile, source_lines

class CitationTests(unittest.TestCase):
    def test_unicode_line_reference_disambiguates_repeated_text(self):
        doc=chr(0x1f600)+" Alpha\nAlpha"
        fields=dict.fromkeys(FIELDS)
        fields["project_name"]={"value":"Alpha","evidenceLineIds":[2]}
        profile=cited_to_profile(doc,"doc-1",fields)
        self.assertEqual(profile["evidence"]["project_name"],[{"documentId":"doc-1","start":8,"end":13}])
    def test_invalid_line_ids_rejected(self):
        for refs in ([0],[4],[True],["1"],[]):
            fields=dict.fromkeys(FIELDS)
            fields["project_name"]={"value":"Alpha","evidenceLineIds":refs}
            with self.subTest(refs=refs),self.assertRaises(AnalysisError):
                cited_to_profile("Alpha","doc-1",fields)
    def test_value_outside_selected_line_rejected(self):
        fields=dict.fromkeys(FIELDS)
        fields["backend"]={"value":["register"],"evidenceLineIds":[2]}
        with self.assertRaises(AnalysisError) as caught:
            cited_to_profile("register\nlogin","doc-1",fields)
        self.assertEqual(caught.exception.code,"EVIDENCE_MISMATCH")
        self.assertEqual(caught.exception.field,"backend")
    def test_crlf_offsets_and_blank_lines(self):
        self.assertEqual(source_lines("A\r\n\r\nB"),[
            {"id":1,"text":"A","start":0,"end":1},
            {"id":2,"text":"","start":3,"end":3},
            {"id":3,"text":"B","start":5,"end":6}])
    def test_empty_array_has_absence_evidence(self):
        fields=dict.fromkeys(FIELDS)
        fields["features"]={"spans":[],"absenceLineIds":[1]}
        self.assertEqual(cited_to_profile("No features.","doc-1",fields)["data"]["features"],[])
