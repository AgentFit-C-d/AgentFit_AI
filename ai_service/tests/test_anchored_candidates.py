import unittest
from agentfit_ai.anchored_candidates import units, candidate_schema, validate_quotes, classify
from agentfit_ai.solar import AnalysisError

class AnchorTests(unittest.TestCase):
    def test_lossless_units(self):
        for document in ("# 제목\r\n가😀\r\n\r\n나\r\n","| a | b |\n|---|---|\n| x | y |\n","~~~py\nx=1\n\nprint(x)\n~~~\n"):
            result=units(document)
            self.assertEqual("".join(s.text for s in result),document)
            for s in result:self.assertEqual(document[s.start:s.end],s.text)
    def test_only_quote_no_classification(self):
        unit=units("Alpha")[0]
        schema=candidate_schema([unit])
        text=str(schema)
        for name in ("role","status","scope","field"):self.assertNotIn("'"+name+"'",text)
        pool=validate_quotes({"units":[{"unitId":unit.id,"quotes":["Alpha"]}]},[unit],0)
        self.assertEqual(pool[0]["span"],{"start":0,"end":5})
        self.assertEqual(set(pool[0]),{"id","unitId","quote","span"})
    def test_coverage_ambiguity_and_duplicates(self):
        unit=units("x x")[0]
        for value in ({"units":[]},{"units":[{"unitId":unit.id,"quotes":["x"]}]},
                      {"units":[{"unitId":unit.id,"quotes":["x x","x x"]}]}):
            with self.assertRaises(AnalysisError):validate_quotes(value,[unit],0)
    def test_classification_absence_unknown_and_exclusion(self):
        source="외부 연동은 없다."
        unit=units(source)[0]
        pool=validate_quotes({"units":[{"unitId":unit.id,"quotes":[source]}]},[unit],0)
        row={"field":"external_integrations","role":"named_service","status":"absent","scope":"current","decision":"selected"}
        result=classify({"decisions":{"F0001":row}},pool,source,"doc")
        self.assertEqual(result["data"]["external_integrations"],[])
        self.assertEqual(result["sources"]["external_integrations"],"DOCUMENT")
        self.assertIsNone(result["data"]["ai"])
        row={**row,"decision":"not_confirmed","status":"tentative"}
        result=classify({"decisions":{"F0001":row}},pool,source,"doc")
        self.assertIsNone(result["data"]["external_integrations"])
    def test_missing_or_invalid_decision_rejected(self):
        unit=units("Alpha")[0]
        pool=validate_quotes({"units":[{"unitId":unit.id,"quotes":["Alpha"]}]},[unit],0)
        with self.assertRaises(AnalysisError):classify({"decisions":{}},pool,"Alpha","doc")
        row={"field":"features","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}
        with self.assertRaises(AnalysisError):classify({"decisions":{"F0001":row}},pool,"Alpha","doc")

    def test_pipeline_has_no_labels_at_extraction_and_counts_calls(self):
        from unittest.mock import Mock
        from test_staged_analysis import response
        from test_semantic_review import verdict
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        source="Alpha"
        replies=[{"units":[{"unitId":"U0001","quotes":["Alpha"]}]},
                 {"decisions":{"F0001":{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}}},
                 verdict()]
        transport=Mock(side_effect=[response(x) for x in replies])
        result=AnchoredAnalyzer("synthetic-key",transport=transport).analyze(source,"doc")
        self.assertEqual(result.provider_calls,3)
        self.assertEqual(result.profile["data"]["project_name"],"Alpha")
        first=transport.call_args_list[0].args[0]["response_format"]["json_schema"]["schema"]
        self.assertNotIn("'role'",str(first))

    def test_irrelevant_has_no_invented_field(self):
        unit=units("Meeting")[0]
        pool=validate_quotes({"units":[{"unitId":unit.id,"quotes":["Meeting"]}]},[unit],0)
        result=classify({"decisions":{"F0001":{"decision":"irrelevant"}}},pool,"Meeting","doc")
        self.assertTrue(all(value is None for value in result["data"].values()))

    def test_repair_respects_six_calls(self):
        from unittest.mock import Mock
        from test_staged_analysis import response
        from test_semantic_review import verdict,issue
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        import json
        reviews=[verdict([issue("overbroad")]),verdict()]
        def transport(payload,*args):
            schema=payload["response_format"]["json_schema"]["schema"]
            if "checkedFields" in schema["properties"]:
                return response(reviews.pop(0))
            content=json.loads(payload["messages"][1]["content"])
            if "units" in content:
                return response({"units":[{"unitId":u["unitId"],"quotes":[v for v in ("Alpha","checkout") if v in u["text"]]} for u in content["units"]]})
            if "candidates" in content:
                return response({"decisions":{c["id"]:{"field":"project_name" if c["quote"]=="Alpha" else "features",
                    "role":"product_fact" if c["quote"]=="Alpha" else "user_action",
                    "status":"confirmed","scope":"current","decision":"selected"} for c in content["candidates"]}})
            return response(reviews.pop(0))
        t=Mock(side_effect=transport)
        result=AnchoredAnalyzer("synthetic-key",transport=t).analyze("# Name\nAlpha\n# Features\ncheckout","doc")
        self.assertEqual(t.call_count,6)
        self.assertEqual(result.provider_calls,6)
        self.assertFalse(result.first_pass_validated)

    def test_capacity_before_network(self):
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        transport=Mock()
        with self.assertRaises(AnalysisError):
            AnchoredAnalyzer("synthetic-key",transport=transport).analyze("x"*24001,"doc")
        transport.assert_not_called()

    def test_missing_fact_outside_pool_fails_without_retry(self):
        from unittest.mock import Mock
        from test_staged_analysis import response
        from test_semantic_review import verdict
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        missing={"field":"database","kind":"missing","itemIndex":None,"evidenceLineIds":[2]}
        replies=[{"units":[{"unitId":"U0001","quotes":["Alpha"]}]},
                 {"decisions":{"F0001":{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}}},
                 verdict([missing]),{"decisions":{"F0001":{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}}},verdict()]
        t=Mock(side_effect=[response(x) for x in replies])
        with self.assertRaises(AnalysisError) as error:
            AnchoredAnalyzer("synthetic-key",transport=t).analyze("Alpha\nSQLite","doc")
        self.assertEqual(error.exception.code,"ANCHORED_MISSING_CANDIDATE")
        self.assertEqual(t.call_count,3)

    def test_missing_field_unchanged_cannot_be_approved(self):
        from unittest.mock import Mock
        from test_staged_analysis import response
        from test_semantic_review import verdict
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        missing={"field":"database","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}
        replies=[{"units":[{"unitId":"U0001","quotes":["Alpha"]}]},
                 {"decisions":{"F0001":{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}}},
                 verdict([missing]),{"decisions":{"F0001":{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"}}},verdict()]
        t=Mock(side_effect=[response(x) for x in replies])
        with self.assertRaises(AnalysisError) as error:
            AnchoredAnalyzer("synthetic-key",transport=t).analyze("Alpha SQLite","doc")
        self.assertEqual(error.exception.code,"ANCHORED_MISSING_CANDIDATE")
        self.assertEqual(t.call_count,4)
