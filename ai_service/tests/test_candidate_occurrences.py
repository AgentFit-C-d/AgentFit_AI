import unittest
from agentfit_ai.anchored_candidates import units, validate_quotes
from agentfit_ai.solar import AnalysisError

def response(batch,quotes):
    return {"units":[{"unitId":u.id,"quotes":[q for q in quotes if q in u.text]} for u in batch]}

class CandidateOccurrenceTests(unittest.TestCase):
    def test_repeated_and_overlapping_positions_are_all_preserved(self):
        batch=units("aaaa")
        pool=validate_quotes(response(batch,["aa"]),batch,0,expand_occurrences=True)
        self.assertEqual([p["span"]["start"] for p in pool],[0,1,2])
        self.assertEqual([p["id"] for p in pool],["F0001","F0002","F0003"])
        with self.assertRaises(AnalysisError):validate_quotes(response(batch,["aa"]),batch,0)

    def test_order_and_global_unicode_crlf_offsets(self):
        doc="# Scope\r\n🦉 Dr. Atlas uses Raven, then Raven."
        batch=units(doc)
        a=validate_quotes(response(batch,["Raven","Dr. Atlas"]),batch,2,expand_occurrences=True)
        b=validate_quotes(response(batch,["Dr. Atlas","Raven"]),batch,2,expand_occurrences=True)
        self.assertEqual(a,b)
        self.assertEqual(a[0]["id"],"F0003")
        for candidate in a:self.assertEqual(doc[candidate["span"]["start"]:candidate["span"]["end"]],candidate["quote"])
        self.assertEqual(a[-1]["span"]["start"],doc.rindex("Raven"))

    def test_capacity_counts_expanded_positions_without_partial_success(self):
        batch=units("a"*120)
        self.assertEqual(len(validate_quotes(response(batch,["a"]),batch,0,expand_occurrences=True)),120)
        for text,start in (("a"*121,0),("aa",119)):
            batch=units(text)
            with self.assertRaises(AnalysisError) as error:validate_quotes(response(batch,["a"]),batch,start,expand_occurrences=True)
            self.assertEqual(error.exception.code,"SECTION_LIMIT")

    def test_existing_structural_guards_remain(self):
        batch=units("A A")
        for quotes in (["A","A"],["missing"],[" "]):
            payload={"units":[{"unitId":batch[0].id,"quotes":quotes}]}
            with self.assertRaises(AnalysisError):validate_quotes(payload,batch,0,expand_occurrences=True)

    def test_focus_is_source_exact_bounded_and_not_a_new_quote(self):
        from agentfit_ai.candidate_occurrences import candidate_views
        doc="x"*170+"Raven"+"y"*170
        batch=units(doc);pool=validate_quotes(response(batch,["Raven"]),batch,0,expand_occurrences=True)
        plain=candidate_views(pool,batch,focus=False)[0]
        self.assertEqual(set(plain),{"id","unitId","quote"})
        focused=candidate_views(pool,batch,focus=True)[0]
        self.assertEqual(focused["focus"],{"before":"x"*160,"selected":"Raven","after":"y"*160})
        self.assertTrue(focused["beforeTruncated"]);self.assertTrue(focused["afterTruncated"])
        self.assertNotIn("span",focused)

    def test_pipeline_passes_focus_and_preserves_original_quote(self):
        import json
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response as api_response
        from test_semantic_review import verdict
        seen=[]
        def transport(payload,*args):
            keys=payload["response_format"]["json_schema"]["schema"]["properties"]
            if "units" in keys:return api_response({"units":[{"unitId":"U0001","quotes":["Raven"]}]})
            if "decisions" in keys:
                content=json.loads(payload["messages"][1]["content"]);seen.extend(content["candidates"])
                decisions={c["id"]:({"field":"ai","role":"operating_model","status":"confirmed","scope":"current","decision":"selected"}
                    if c["focus"]["before"].endswith("운영 ") else {"decision":"irrelevant"}) for c in seen}
                return api_response({"decisions":decisions})
            return api_response(verdict())
        doc="개발 Raven, 운영 Raven"
        t=Mock(side_effect=transport)
        result=AnchoredAnalyzer("synthetic-key",transport=t,prompt_revision="v2",candidate_occurrences=True).analyze(doc,"doc")
        self.assertEqual(len(seen),2)
        self.assertEqual(result.profile["data"]["ai"],["Raven"])
        self.assertEqual(result.profile["evidence"]["ai"][0]["start"],doc.rindex("Raven"))
        self.assertEqual(result.provider_calls,3)
        self.assertIn("candidate-occurrences-v1",result.prompt_version)
        with self.assertRaises(ValueError):AnchoredAnalyzer("synthetic-key",candidate_occurrences=True)

    def test_overflow_stops_before_judgment_network_call(self):
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response as api_response
        t=Mock(return_value=api_response({"units":[{"unitId":"U0001","quotes":["Raven"]}]}))
        with self.assertRaises(AnalysisError) as error:
            AnchoredAnalyzer("synthetic-key",transport=t,prompt_revision="v2",candidate_occurrences=True).analyze("Raven "*121,"doc")
        self.assertEqual(error.exception.code,"SECTION_LIMIT")
        self.assertEqual(t.call_count,1)
