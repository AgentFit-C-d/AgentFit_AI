import unittest
from agentfit_ai.semantic_review import validate_review, ReviewValidationError
from agentfit_ai.profile import FIELDS
from agentfit_ai.anchored_evaluation import safe_diagnostics

class ReviewDiagnosticTests(unittest.TestCase):
    def test_invalid_contract_reasons_preserve_error_code(self):
        profile={"data":dict.fromkeys(FIELDS)}
        profile["data"]["features"]=["action"]
        issue={"field":"features","kind":"overbroad","itemIndex":0,"evidenceLineIds":[1]}
        valid={"checkedFields":list(FIELDS),"issues":[]}
        cases=[
            ({}, "ROOT_SHAPE"),
            ({**valid,"checkedFields":[]}, "CHECKED_FIELDS"),
            ({**valid,"issues":{}}, "ISSUES_SHAPE"),
            ({**valid,"issues":[{}]}, "ISSUE_SHAPE"),
            ({**valid,"issues":[{**issue,"field":"private text"}]}, "ISSUE_ENUM"),
            ({**valid,"issues":[{**issue,"evidenceLineIds":[2]}]}, "EVIDENCE_LINES"),
            ({**valid,"issues":[{**issue,"kind":"missing"}]}, "MISSING_INDEX"),
            ({**valid,"issues":[{**issue,"field":"ai","itemIndex":None}]}, "NULL_NON_MISSING"),
            ({**valid,"issues":[{**issue,"itemIndex":None}]}, "ARRAY_INDEX"),
        ]
        for reply,reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(ReviewValidationError) as caught:
                    validate_review(reply,profile,1)
                self.assertEqual(str(caught.exception),"SEMANTIC_REVIEW_INVALID")
                self.assertEqual(caught.exception.reason,reason)
        profile["data"]["features"]=[]
        with self.assertRaises(ReviewValidationError) as caught:
            validate_review({**valid,"issues":[issue]},profile,1)
        self.assertEqual(caught.exception.reason,"SCALAR_INDEX")
        self.assertEqual(validate_review(valid,profile,1),[])

    def test_only_known_review_reason_is_exported(self):
        result=safe_diagnostics({"calls":[
            {"review_error":{"reason":"ARRAY_INDEX","raw":"private"}},
            {"review_error":{"reason":"COMPACT_MISSING_SOURCE_EMPTY","raw":"private"}},
            {"review_error":{"reason":"private"}},
        ]})
        self.assertEqual(result["calls"],[{"review_error":{"reason":"ARRAY_INDEX"}},
                                          {"review_error":{"reason":"COMPACT_MISSING_SOURCE_EMPTY"}},{}])

    def test_section_review_reasons_are_exported_without_raw_values(self):
        for reason in ("CHECKED_RANGE", "SECTION_SOURCE_LINE_INVALID",
                       "SECTION_TARGET_INVALID", "SECTION_ISSUE_CONFLICT",
                       "SECTION_EVIDENCE_ALIGNMENT"):
            with self.subTest(reason=reason):
                result = safe_diagnostics({"calls": [
                    {"review_error": {"reason": reason, "raw": "private"}}]})
                self.assertEqual(result["calls"],
                                 [{"review_error": {"reason": reason}}])

    def test_anchored_error_reaches_safe_diagnostics(self):
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from agentfit_ai.solar import AnalysisError
        from test_staged_analysis import response
        t=Mock(side_effect=[
            response({"units":[{"unitId":"U0001","quotes":[]}]}),
            response({"checkedFields":list(FIELDS),"issues":[
                {"field":"features","kind":"overbroad","itemIndex":None,"evidenceLineIds":[1]}]}),
        ])
        with self.assertRaises(AnalysisError) as caught:
            AnchoredAnalyzer("synthetic-key",transport=t).analyze("meeting","doc")
        self.assertEqual(caught.exception.code,"SEMANTIC_REVIEW_INVALID")
        calls=safe_diagnostics(caught.exception.diagnostics)["calls"]
        self.assertEqual(calls[-1]["review_error"],{"reason":"NULL_NON_MISSING"})
