import unittest
from copy import deepcopy
from agentfit_ai.source_repair import apply_repairs, repair_schema
from agentfit_ai.anchored_candidates import units
from agentfit_ai.solar import AnalysisError
from test_source_repair import empty, fact, reply

def indexed(quote,index=1,role="operating_model",status="confirmed",unitId="U0001"):
    value=fact(quote,role,status,unitId=unitId)
    del value["context"]
    value["occurrenceIndex"]=index
    return value

class RepairOccurrenceTests(unittest.TestCase):
    def test_repeat_uses_requested_global_occurrence(self):
        doc="# Scope\r\n🦉 개발은 Raven, 운영도 Raven."
        sections=units(doc)
        target=next(s for s in sections if "Raven" in s.text)
        result=apply_repairs(doc,"doc",empty(doc),sections,["ai"],
            reply("ai",[indexed("Raven",2,unitId=target.id)]),occurrence_index=True)
        self.assertEqual(result["data"]["ai"],["Raven"])
        self.assertEqual(result["evidence"]["ai"][0]["start"],doc.rindex("Raven"))
        self.assertEqual(result["evidence"]["ai"][0]["end"],doc.rindex("Raven")+5)

    def test_invalid_index_and_old_contract_are_rejected_atomically(self):
        doc="Raven Raven";old=empty(doc);before=deepcopy(old)
        for index in (0,-1,3,24001,True,1.0,"2",None):
            with self.subTest(index=index),self.assertRaises(AnalysisError):
                apply_repairs(doc,"doc",old,units(doc),["ai"],reply("ai",[indexed("Raven",index)]),occurrence_index=True)
            self.assertEqual(old,before)
        for value in (fact("Raven"),dict(indexed("Raven"),context=None),{k:v for k,v in indexed("Raven").items() if k!="occurrenceIndex"}):
            with self.assertRaises(AnalysisError):
                apply_repairs(doc,"doc",old,units(doc),["ai"],reply("ai",[value]),occurrence_index=True)
        with self.assertRaises(AnalysisError):
            apply_repairs(doc,"doc",old,units(doc),["ai"],reply("ai",[indexed("Raven",2)]))

    def test_nonoverlap_absence_and_abbreviation(self):
        doc="aaaa"
        result=apply_repairs(doc,"doc",empty(doc),units(doc),["project_name"],
            reply("project_name",[indexed("aa",2,role="product_fact")]),occurrence_index=True)
        self.assertEqual(result["evidence"]["project_name"][0]["start"],2)
        for doc,field,value in [("제품 Dr. Atlas","project_name",indexed("Dr. Atlas",role="product_fact")),
                               ("운영 AI 없음","ai",indexed("운영 AI 없음",status="absent"))]:
            result=apply_repairs(doc,"doc",empty(doc),units(doc),[field],reply(field,[value]),occurrence_index=True)
            self.assertEqual(result["data"][field],[] if field=="ai" else "Dr. Atlas")

    def test_duplicates_and_blank_or_missing_quotes_fail(self):
        doc="Raven Raven"
        for facts in ([indexed("Raven"),indexed("Raven")],[indexed("Missing")],[indexed(" ")]):
            with self.assertRaises(AnalysisError):
                apply_repairs(doc,"doc",empty(doc),units(doc),["ai"],reply("ai",facts),occurrence_index=True)

    def test_schema_requires_index_only_when_enabled(self):
        for enabled in (False,True):
            schema=repair_schema(["ai"],units("Raven"),occurrence_index=enabled)
            fact_schema=schema["properties"]["repairs"]["properties"]["ai"]["properties"]["facts"]["items"]
            self.assertEqual("occurrenceIndex" in fact_schema["required"],enabled)
            self.assertEqual("context" in fact_schema["properties"],not enabled)

    def test_analyzer_uses_index_only_in_repair_and_rejects_split_combination(self):
        import json
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response
        from test_semantic_review import verdict
        doc="개발 Raven, 운영 Raven"
        issues=[{"field":"ai","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
        t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
            response(verdict(issues)),response(reply("ai",[indexed("Raven",2)])),response(verdict())])
        result=AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True,
            repair_occurrence_index=True,repair_examples=True,repair_value_boundary=True,
            repair_state_grounding=True).analyze(doc,"doc")
        self.assertEqual(result.provider_calls,4)
        self.assertEqual(result.profile["evidence"]["ai"][0]["start"],doc.rindex("Raven"))
        self.assertIn("occurrence-v1",result.prompt_version)
        prompt=t.call_args_list[2].args[0]["messages"][0]["content"]
        self.assertNotIn("context",prompt)
        self.assertIn('"quote":"Finch","occurrenceIndex":2',prompt)
        for kwargs in ({"repair_occurrence_index":True},{"source_repair":True,"repair_occurrence_index":True,"repair_evidence_units":True}):
            with self.assertRaises(ValueError):AnchoredAnalyzer("synthetic-key",**kwargs)

    def test_evidence_scoring_rejects_right_value_wrong_occurrence(self):
        from agentfit_ai.value_repair_evaluation import score_evidence
        doc="Raven Raven"
        result=apply_repairs(doc,"doc",empty(doc),units(doc),["ai"],reply("ai",[indexed("Raven",1)]),occurrence_index=True)
        self.assertEqual(result["data"]["ai"],["Raven"])
        self.assertFalse(score_evidence(result,{"ai":[{"start":6,"end":11}]})["evidence_matched"])
        self.assertTrue(score_evidence(result,{"ai":[{"start":0,"end":5}]})["evidence_matched"])
