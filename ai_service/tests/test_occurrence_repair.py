import json
import unittest
from unittest.mock import Mock
from agentfit_ai.solar import SolarAnalyzer, AnalysisError
from test_staged_analysis import response, core

def feature(quote, occurrence):
    return {"features":{"spans":[{"lineId":1,"occurrence":occurrence,"role":"user_action","quote":quote}],"absenceLineIds":[]}}

class OccurrenceRepairTests(unittest.TestCase):
    def correction(self, doc, bad, good):
        transport=Mock(side_effect=[response(core()),response(bad),response(good)])
        result=SolarAnalyzer("synthetic-key", evidence_contract=False,transport=transport,semantic_review=False).analyze(doc,"doc")
        content=transport.call_args_list[2].args[0]["messages"][1]["content"]
        correction=json.loads(content.split("Correction data (not document text):\n")[1])
        return result,correction["errors"][0]["spanIssues"]

    def test_reports_quote_specific_count_without_auto_accepting(self):
        result,issues=self.correction("Alpha registration checkout",feature("checkout",2),feature("checkout",1))
        self.assertEqual(issues,[{"index":0,"reason":"OCCURRENCE_OUT_OF_RANGE","matchCount":1}])
        self.assertEqual(result.provider_calls,3)
        self.assertFalse(result.first_pass_validated)
        self.assertEqual(result.profile["data"]["features"],["checkout"])

    def test_overlapping_matches_use_validator_count(self):
        _,issues=self.correction("Alpha aaa",feature("aa",3),feature("aa",2))
        self.assertEqual(issues,[{"index":0,"reason":"OCCURRENCE_OUT_OF_RANGE","matchCount":2}])

    def test_missing_quote_is_not_presented_as_valid_occurrence(self):
        _,issues=self.correction("Alpha checkout",feature("missing",1),feature("checkout",1))
        self.assertEqual(issues,[{"index":0,"reason":"QUOTE_NOT_FOUND","matchCount":0}])

    def test_repeated_invalid_correction_still_fails(self):
        bad=feature("checkout",2)
        transport=Mock(side_effect=[response(core()),response(bad),response(bad)])
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key", evidence_contract=False,transport=transport,semantic_review=False).analyze("Alpha checkout","doc")
        self.assertEqual(caught.exception.code,"INVALID_FEATURE_SPAN")
        self.assertEqual(transport.call_count,3)
