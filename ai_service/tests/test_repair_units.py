import unittest
from agentfit_ai.repair_units import split_repair_units
from agentfit_ai.anchored_candidates import units
from agentfit_ai.sections import SectionError
from agentfit_ai.source_repair import apply_repairs
from agentfit_ai.solar import AnalysisError
from test_source_repair import empty, fact, reply

class RepairUnitTests(unittest.TestCase):
    def test_lossless_offsets_with_crlf_headings_and_punctuation(self):
        doc="# Scope\r\nFirst A. Second A!\r\nNext? End.\r\n"
        result=split_repair_units(units(doc))
        self.assertEqual("".join(s.text for s in result),doc)
        self.assertEqual([s.id for s in result],["U"+str(i+1).zfill(4) for i in range(len(result))])
        for section in result:self.assertEqual(doc[section.start:section.end],section.text)
        self.assertEqual(result[0].start,0)
        self.assertEqual(result[-1].end,len(doc))
        self.assertTrue(all(a.end==b.start for a,b in zip(result,result[1:])))

    def test_url_and_decimal_are_not_split_at_internal_dots(self):
        doc="Use https://sample.test/a and 3.14. Next."
        result=split_repair_units(units(doc))
        self.assertEqual([s.text for s in result],["Use https://sample.test/a and 3.14. ","Next."])
        # Abbreviations can split; no characters are discarded or synthesized.
        doc="Mr. Smith chooses A."
        self.assertEqual("".join(s.text for s in split_repair_units(units(doc))),doc)

    def test_same_name_can_anchor_to_operating_sentence(self):
        doc="Dev uses Raven. Operations use Raven."
        result=split_repair_units(units(doc))
        repaired=apply_repairs(doc,"doc",empty(doc),result,["ai"],
            reply("ai",[fact("Raven","operating_model",unitId=result[1].id)]))
        self.assertEqual(repaired["data"]["ai"],["Raven"])
        self.assertEqual(repaired["evidence"]["ai"][0]["start"],doc.rindex("Raven"))

    def test_ambiguity_inside_one_unit_and_cross_unit_quote_still_fail(self):
        for doc,quote in [("Raven Raven","Raven"),("First. Second.","First. Second.")]:
            sections=split_repair_units(units(doc))
            with self.assertRaises(AnalysisError):
                apply_repairs(doc,"doc",empty(doc),sections,["features"],
                    reply("features",[fact(quote,unitId=sections[0].id)]))

    def test_limit_never_returns_partial_units(self):
        self.assertEqual(len(split_repair_units(units("A. "*400))),400)
        with self.assertRaises(SectionError) as caught:split_repair_units(units("A. "*401))
        self.assertEqual(str(caught.exception),"SECTION_LIMIT")

    def test_only_repair_request_uses_subunits_and_offsets_stay_global(self):
        import json
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response
        from test_semantic_review import verdict
        doc="Dev uses Raven. Operations use Raven."
        for enabled in (False,True):
            seen={}
            def transport(payload,*args):
                schema=payload["response_format"]["json_schema"]["schema"]["properties"]
                if "units" in schema:
                    seen["initial"]=json.loads(payload["messages"][1]["content"])["units"]
                    return response({"units":[{"unitId":u["unitId"],"quotes":[]} for u in seen["initial"]]})
                if "repairs" in schema:
                    seen["repair"]=json.loads(payload["messages"][1]["content"])["units"]
                    target=next(u for u in seen["repair"] if "Operations" in u["text"])
                    return response(reply("ai",[fact("Raven","operating_model",unitId=target["unitId"],context="Operations use Raven.")]))
                issues=[] if "repair" in seen else [{"field":"ai","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
                return response(verdict(issues))
            result=AnchoredAnalyzer("synthetic-key",transport=Mock(side_effect=transport),source_repair=True,
                repair_state_grounding=True,repair_evidence_units=enabled).analyze(doc,"doc")
            self.assertEqual(len(seen["initial"]),1)
            self.assertEqual(len(seen["repair"]),2 if enabled else 1)
            self.assertEqual(result.profile["evidence"]["ai"][0]["start"],doc.rindex("Raven"))
            self.assertEqual(result.provider_calls,4)
            self.assertEqual("repair-units-v1" in result.prompt_version,enabled)

    def test_limit_fails_before_sending_any_partial_repair(self):
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response
        from test_semantic_review import verdict
        t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
            response(verdict([{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]))])
        with self.assertRaises(AnalysisError) as caught:
            AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True,repair_evidence_units=True).analyze("A. "*401,"doc")
        self.assertEqual(caught.exception.code,"SECTION_LIMIT")
        self.assertEqual(t.call_count,2)

    def test_low_reasoning_is_limited_to_source_repair(self):
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response
        from test_semantic_review import verdict
        issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
        t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
            response(verdict(issues)),response(reply("features",[fact("search")])),response(verdict())])
        result=AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True,repair_effort="low",
            review_effort="low").analyze("search","doc")
        payloads=[c.args[0] for c in t.call_args_list]
        self.assertEqual([p["reasoning_effort"] for p in payloads],["none","low","low","low"])
        self.assertEqual(payloads[2]["max_tokens"],4096)
        self.assertIn("repair-low",result.prompt_version)
        with self.assertRaises(ValueError):AnchoredAnalyzer("synthetic-key",repair_effort="low")
