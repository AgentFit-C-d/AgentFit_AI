import json
import unittest
from unittest.mock import Mock

from agentfit_ai.profile import FIELDS
from agentfit_ai.source_selector_analysis import SourceSelectorSolarAnalyzer
from test_semantic_review import verdict
from test_staged_analysis import response


def confirmed(line_id, selector="BODY", role="product_fact"):
    return {"state": "confirmed", "items": [
        {"lineId": line_id, "selector": selector, "role": role}]}


def core(selector="BODY"):
    fields = {field: None for field in FIELDS if field != "features"}
    fields["project_name"] = confirmed(1, selector)
    return fields


def features():
    return {"features": confirmed(2, role="user_action")}


class SourceSelectorAnalysisTests(unittest.TestCase):
    def test_first_pass_selects_server_owned_spans_without_value(self):
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response(verdict())])
        analyzer = SourceSelectorSolarAnalyzer("synthetic-key", transport=transport)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(result["profile"]["data"]["features"], ["registration"])
        self.assertEqual(transport.call_count, 3)
        for call in transport.call_args_list[:2]:
            payload = call.args[0]
            self.assertIn("[L1] # Alpha", payload["messages"][1]["content"])
            schema = payload["response_format"]["json_schema"]["schema"]
            self.assertNotIn("value", json.dumps(schema))
            self.assertIn("selector", json.dumps(schema))

    def test_invalid_selector_repairs_without_model_value(self):
        transport = Mock(side_effect=[response(core("BOLD_1")), response(features()),
                                      response({"project_name": confirmed(1)}),
                                      response(verdict())])
        analyzer = SourceSelectorSolarAnalyzer("synthetic-key", transport=transport)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 4)
        payload = transport.call_args_list[2].args[0]
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]["required"],
                         ["project_name"])
        self.assertIn("INVALID_SELECTOR", payload["messages"][1]["content"])
        self.assertEqual(analyzer._contract_version(), "source-selector-v1")
