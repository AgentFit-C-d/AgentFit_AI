import unittest
from agentfit_ai.section_analysis import validate_candidates,extraction_schema
from agentfit_ai.sections import split_sections
from agentfit_ai.solar import AnalysisError

def item(quote="checkout",field="features",role="user_action",status="confirmed",context=None):
    return dict(field=field,quote=quote,context=context,role=role,status=status,scope="current")
def reply(*items):
    return {"sections":[{"sectionId":"S0001","facts":list(items)}]}

class QuoteExtractionTests(unittest.TestCase):
    def parse(self,doc,r):
        try:return validate_candidates(r,split_sections(doc),0,quote_only=True)
        except TypeError:self.fail("quote-only contract missing")
    def test_value_comes_from_exact_source(self):
        pool=self.parse("기능: checkout",reply(item()))
        self.assertEqual(pool[0]["value"],"checkout")
        self.assertEqual(pool[0]["span"],{"start":4,"end":12})
    def test_absence_has_evidence_but_no_value(self):
        pool=self.parse("외부 연동 없음",reply(item("외부 연동 없음","external_integrations","named_service","absent")))
        self.assertIsNone(pool[0]["value"])
    def test_long_confirmed_quote_is_rejected(self):
        with self.assertRaises(AnalysisError) as c:self.parse("x"*201,reply(item("x"*201)))
        self.assertEqual(c.exception.candidate_detail["reason"],"QUOTE_TOO_LONG")
    def test_missing_quote_has_safe_specific_reason(self):
        with self.assertRaises(AnalysisError) as c:self.parse("checkout",reply(item("refund")))
        self.assertEqual(c.exception.candidate_detail,{"reason":"QUOTE_NOT_FOUND","sectionId":"S0001","itemIndex":0})
    def test_repeated_quote_requires_unique_context(self):
        with self.assertRaises(AnalysisError) as c:self.parse("A checkout B checkout",reply(item()))
        self.assertEqual(c.exception.candidate_detail["reason"],"AMBIGUOUS_QUOTE")
        pool=self.parse("A checkout B checkout",reply(item(context="B checkout")))
        self.assertEqual(pool[0]["span"]["start"],13)
    def test_schema_excludes_independent_value(self):
        try:s=extraction_schema(split_sections("checkout"),quote_only=True)
        except TypeError:self.fail("quote-only schema missing")
        self.assertNotIn("value",s["properties"]["sections"]["items"]["properties"]["facts"]["items"]["properties"])
    def test_section_coverage_distinguishes_missing_and_duplicate(self):
        for r,reason in [({"sections":[]},"MISSING_SECTION"),
                         ({"sections":[{"sectionId":"S0001","facts":[]},{"sectionId":"S0001","facts":[]}]},"DUPLICATE_SECTION")]:
            with self.assertRaises(AnalysisError) as c:self.parse("checkout",r)
            self.assertEqual(c.exception.candidate_detail["reason"],reason)
    def test_legacy_value_mismatch_remains_distinct(self):
        x=item();x["value"]="refund"
        with self.assertRaises(AnalysisError) as c:validate_candidates(reply(x),split_sections("checkout"),0)
        self.assertEqual(c.exception.candidate_detail["reason"],"VALUE_NOT_IN_QUOTE")

    def test_opt_in_pipeline_records_safe_candidate_error(self):
        from unittest.mock import Mock
        from agentfit_ai.section_analysis import SectionAnalyzer
        from test_staged_analysis import response
        t=Mock(return_value=response(reply(item("refund"))))
        a=SectionAnalyzer("synthetic-key",transport=t,quote_only=True,jev_merge=True)
        with self.assertRaises(AnalysisError) as c:a.analyze("checkout","doc")
        detail=c.exception.diagnostics["calls"][0]["candidate_error"]
        self.assertEqual(detail,{"reason":"QUOTE_NOT_FOUND","sectionId":"S0001","itemIndex":0})
        self.assertNotIn("refund",str(detail))
    def test_quote_pipeline_completes_with_jev(self):
        from unittest.mock import Mock
        from agentfit_ai.section_analysis import SectionAnalyzer
        from test_staged_analysis import response
        from test_semantic_review import verdict
        from test_jev_integration import jev_response
        t=Mock(side_effect=[response(reply(item())),response(verdict())])
        a=SectionAnalyzer("synthetic-key",transport=t,quote_only=True,jev_merge=True,
                          jev_transport=Mock(return_value=jev_response()))
        result=a.analyze("checkout","doc")
        self.assertEqual(result.profile["data"]["features"],["checkout"])
        self.assertEqual(result.prompt_version,"section-v3-jev")
        schema=t.call_args_list[0].args[0]["response_format"]["json_schema"]["schema"]
        self.assertNotIn("value",schema["properties"]["sections"]["items"]["properties"]["facts"]["items"]["properties"])

    def test_gate_rejects_wrong_occurrence_for_operational_action(self):
        import json
        from agentfit_ai.quote_evaluation import CASES,score
        case=json.loads(CASES.read_text(encoding="utf-8"))[1]
        context="사용자는 회원 승인을 요청한다."
        a=item("회원 승인",context=context)
        b=item("회원 승인",role="operational_action",context=context)
        pool=self.parse(case["document"],reply(a,b))
        self.assertFalse(score(pool,case))
        b["context"]="운영자는 회원 승인을 처리한다."
        self.assertTrue(score(self.parse(case["document"],reply(a,b)),case))
    def test_gate_rejects_wrong_role_for_absence(self):
        import json
        from agentfit_ai.quote_evaluation import CASES,score
        case=json.loads(CASES.read_text(encoding="utf-8"))[3]
        pool=self.parse(case["document"],reply(item(case["document"],"external_integrations","product_fact","absent")))
        self.assertFalse(score(pool,case))
