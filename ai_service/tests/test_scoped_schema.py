import unittest
from unittest.mock import Mock
from agentfit_ai.solar import SolarAnalyzer
from test_staged_analysis import response, core, features

class ScopedSchemaTests(unittest.TestCase):
    def test_line_bounds_follow_each_document_on_reused_analyzer(self):
        transport=Mock(side_effect=[response(core()),response(features()),
                                  response(core()),response(features(3))])
        analyzer=SolarAnalyzer("synthetic-key", evidence_contract=False, semantic_review=False,transport=transport)
        analyzer.analyze("Alpha registration","doc-1")
        analyzer.analyze("Alpha\n\nregistration","doc-2")
        for index,maximum in ((0,1),(2,3)):
            schema=transport.call_args_list[index].args[0]["response_format"]["json_schema"]["schema"]
            refs=schema["properties"]["backend"]["anyOf"][1]["properties"]["evidenceLineIds"]
            self.assertEqual(refs.get("minItems"),1)
            self.assertEqual(refs["items"].get("maximum"),maximum)
            self.assertEqual(refs["items"]["minimum"],1)

    def test_features_schema_requires_either_spans_or_absence(self):
        transport=Mock(side_effect=[response(core()),response(features())])
        SolarAnalyzer("synthetic-key", evidence_contract=False, semantic_review=False,transport=transport).analyze("Alpha registration","doc-1")
        schema=transport.call_args_list[1].args[0]["response_format"]["json_schema"]["schema"]
        variants=schema["properties"]["features"]["anyOf"]
        self.assertEqual(len(variants),3)
        present,absent=variants[1]["properties"],variants[2]["properties"]
        self.assertEqual(present["spans"].get("minItems"),1)
        self.assertEqual(present["absenceLineIds"]["maxItems"],0)
        self.assertEqual(absent["spans"]["maxItems"],0)
        self.assertEqual(absent["absenceLineIds"].get("minItems"),1)
        self.assertEqual(present["spans"]["items"]["properties"]["lineId"].get("maximum"),1)

    def test_repair_schema_keeps_document_bounds(self):
        transport=Mock(side_effect=[response(core()),response(features(2)),response(features())])
        SolarAnalyzer("synthetic-key", evidence_contract=False, semantic_review=False,transport=transport).analyze("Alpha registration","doc-1")
        schema=transport.call_args_list[2].args[0]["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["required"],["features"])
        span=schema["properties"]["features"]["anyOf"][1]["properties"]["spans"]["items"]
        self.assertEqual(span["properties"]["lineId"].get("maximum"),1)
