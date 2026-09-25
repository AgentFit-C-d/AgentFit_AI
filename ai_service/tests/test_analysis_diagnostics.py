import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError, candidate_to_profile, provider_to_candidate

class DiagnosticTests(unittest.TestCase):
    def test_mismatch_preserves_field_without_content(self):
        data=dict.fromkeys(FIELDS)
        data["features"]=["PRIVATE_VALUE"]
        quotes={f:[] for f in FIELDS}
        quotes["features"]=["source text"]
        with self.assertRaises(AnalysisError) as caught:
            candidate_to_profile("source text","doc-1",{"data":data,"evidenceQuotes":quotes})
        self.assertEqual(caught.exception.code,"EVIDENCE_MISMATCH")
        self.assertEqual(caught.exception.field,"features")
        self.assertEqual(str(caught.exception),"EVIDENCE_MISMATCH")
        self.assertNotIn("PRIVATE_VALUE",repr(caught.exception))

    def test_missing_quote_preserves_field(self):
        data=dict.fromkeys(FIELDS)
        data["project_name"]="Alpha"
        quotes={f:[] for f in FIELDS}
        quotes["project_name"]=["missing quote"]
        with self.assertRaises(AnalysisError) as caught:
            candidate_to_profile("Alpha","doc-1",{"data":data,"evidenceQuotes":quotes})
        self.assertEqual(caught.exception.field,"project_name")
        self.assertEqual(caught.exception.code,"EVIDENCE_NOT_FOUND")

    def test_untrusted_field_is_not_exposed(self):
        error=AnalysisError("INVALID_RESPONSE","private arbitrary field")
        self.assertIsNone(error.field)
        self.assertEqual(str(error),"INVALID_RESPONSE")

    def test_invalid_known_object_preserves_safe_field(self):
        candidate=dict.fromkeys(FIELDS)
        candidate["backend"]={"value":None,"evidenceQuotes":[]}
        with self.assertRaises(AnalysisError) as caught:
            provider_to_candidate(candidate)
        self.assertEqual(caught.exception.field,"backend")

if __name__=="__main__":
    unittest.main()
