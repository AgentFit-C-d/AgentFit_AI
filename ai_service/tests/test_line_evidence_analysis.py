import json
import unittest
from unittest.mock import Mock

from agentfit_ai.line_evidence_analysis import LineEvidenceSolarAnalyzer
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError, SolarAnalyzer
from test_semantic_review import verdict
from test_staged_analysis import response


def fact(value, line_id=1, role="product_fact"):
    return {"value": value, "lineId": line_id, "role": role}


def confirmed(*items):
    return {"state": "confirmed", "items": list(items)}


def core(name="Alpha"):
    fields = {field: None for field in FIELDS if field != "features"}
    fields["project_name"] = confirmed(fact(name))
    return fields


def features():
    return {"features": confirmed(fact("registration", role="user_action"))}


class LineEvidenceAnalysisTests(unittest.TestCase):
    def test_failed_repair_reports_safe_line_error_without_model_value(self):
        transport = Mock(side_effect=[response(core("Alfa")),
                                      response({"features": None}),
                                      response({"project_name": core("Alfa")["project_name"]})])
        with self.assertRaises(AnalysisError) as caught:
            LineEvidenceSolarAnalyzer("synthetic-key", transport=transport).analyze(
                "Alpha registration", "doc")
        last = caught.exception.diagnostics["calls"][-1]
        self.assertEqual(last["validation_error"]["reason"], "VALUE_NOT_IN_LINE")
        self.assertNotIn("Alfa", json.dumps(last))

    def test_diagnostics_identify_line_contract(self):
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response(verdict())])
        result = LineEvidenceSolarAnalyzer("synthetic-key", transport=transport).analyze(
            "Alpha registration", "doc")
        self.assertEqual(result.diagnostics["evidence_contract"], "line-evidence-v1")

    def test_first_pass_uses_only_line_id_and_exact_value(self):
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response(verdict())])
        analyzer = LineEvidenceSolarAnalyzer("synthetic-key", transport=transport)
        result = analyzer.analyze_recoverable("Alpha registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(result["profile"]["data"]["features"], ["registration"])
        self.assertEqual(transport.call_count, 3)
        for call in transport.call_args_list[:2]:
            payload = call.args[0]
            self.assertIn("[L1] Alpha registration", payload["messages"][1]["content"])
            schema = payload["response_format"]["json_schema"]["schema"]
            self.assertNotIn("quote", json.dumps(schema))
            self.assertNotIn("context", json.dumps(schema))
            self.assertIn("lineId", json.dumps(schema))
        self.assertEqual(analyzer.analyze.__qualname__, SolarAnalyzer.analyze.__qualname__)

    def test_invalid_first_value_is_repaired_under_same_contract(self):
        transport = Mock(side_effect=[response(core("Alfa")), response(features()),
                                      response({"project_name": core()["project_name"]}),
                                      response(verdict())])
        result = LineEvidenceSolarAnalyzer(
            "synthetic-key", transport=transport).analyze_recoverable(
                "Alpha registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 4)
        payload = transport.call_args_list[2].args[0]
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]["required"],
                         ["project_name"])
        self.assertNotIn("quote", json.dumps(payload["response_format"]))
        self.assertIn("VALUE_NOT_IN_LINE", payload["messages"][1]["content"])

    def test_invalid_repair_keeps_only_verified_suggestion(self):
        transport = Mock(side_effect=[response(core("Alfa")), response(features()),
                                      response({"project_name": core("Alfa")["project_name"]})])
        result = LineEvidenceSolarAnalyzer(
            "synthetic-key", transport=transport).analyze_recoverable(
                "Alpha registration", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["fieldStates"]["project_name"], "unresolved")
        self.assertEqual(result["fieldStates"]["features"], "suggested")
        self.assertIsNone(result["profile"]["data"]["project_name"])
        self.assertEqual(result["profile"]["data"]["features"], ["registration"])
        self.assertNotIn("Alfa", json.dumps(result))

    def test_basic_solar_analyzer_keeps_quote_schema(self):
        from agentfit_ai.evidence import evidence_schema
        basic = SolarAnalyzer("synthetic-key")
        self.assertTrue(basic._evidence_contract)
        self.assertIn("quote", json.dumps(evidence_schema()))
