import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from agentfit_ai.name_stability import evaluate_cases

def sample():
    data=dict.fromkeys(FIELDS)
    data["project_name"]="Alpha"
    return {"id":"case-1","document":"Alpha project","expected":data}

def result(data):
    return SimpleNamespace(profile={"data":data},model="solar-pro4-260806",
                           prompt_tokens=10,completion_tokens=20,elapsed_ms=30)

class StabilityEvaluationTests(unittest.TestCase):
    def test_failure_then_success_keeps_both_attempts(self):
        case=sample()
        analyzer=Mock()
        analyzer.analyze.side_effect=[AnalysisError("EVIDENCE_MISMATCH", "backend"),result(case["expected"])]
        report=evaluate_cases([case],analyzer,repeats=2,workers=1)
        self.assertEqual(analyzer.analyze.call_count,2)
        self.assertEqual(report["attempts"],2)
        self.assertEqual(report["passed"],1)
        self.assertEqual(report["name_passed"],1)
        self.assertFalse(report["cases"][0]["passed"])
        self.assertEqual(report["cases"][0]["error"],"EVIDENCE_MISMATCH")
        self.assertEqual(report["cases"][0]["field"],"backend")

    def test_wrong_name_is_failure_and_report_contains_no_content(self):
        case=sample()
        wrong=dict(case["expected"],project_name="sensitive-provider-content")
        analyzer=Mock()
        analyzer.analyze.return_value=result(wrong)
        report=evaluate_cases([case],analyzer,repeats=2,workers=1)
        self.assertEqual(report["passed"],0)
        self.assertEqual(report["name_passed"],0)
        self.assertEqual(report["cases"][0]["mismatch_fields"],["project_name"])
        self.assertNotIn("sensitive-provider-content",json.dumps(report))
        self.assertNotIn("Alpha",json.dumps(report))

    def test_other_field_regression_cannot_count_as_full_success(self):
        case=sample()
        analyzer=Mock()
        analyzer.analyze.return_value=result(dict(case["expected"],database="SQLite"))
        report=evaluate_cases([case],analyzer,repeats=2,workers=1)
        self.assertEqual(report["name_passed"],2)
        self.assertEqual(report["passed"],0)
        self.assertEqual(report["cases"][0]["name_span"],{"start":0,"end":5})

    def test_expected_null_is_not_counted_as_extraction_error(self):
        case=sample()
        case["expected"]["project_name"]=None
        analyzer=Mock()
        analyzer.analyze.return_value=result(case["expected"])
        report=evaluate_cases([case],analyzer,repeats=2,workers=1)
        self.assertEqual(report["passed"],2)
        self.assertEqual(report["name_passed"],2)
        self.assertIsNone(report["cases"][0]["name_span"])

if __name__=="__main__":
    unittest.main()
