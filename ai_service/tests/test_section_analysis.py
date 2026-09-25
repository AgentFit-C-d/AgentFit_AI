import unittest
from unittest.mock import Mock
from agentfit_ai.section_analysis import SectionAnalyzer
from agentfit_ai.solar import AnalysisError
from agentfit_ai.profile import FIELDS
from test_staged_analysis import response
from test_semantic_review import verdict,issue

def fact(field,value,role="product_fact",status="confirmed",scope="current"):
    return {"field":field,"value":value,"quote":value or "none","context":None,"role":role,"status":status,"scope":scope}
def extraction(sid,*facts):
    return {"sections":[{"sectionId":sid,"facts":list(facts)}]}
def selection(fields=None,excluded=None):
    return {"fields":dict(dict.fromkeys(FIELDS),**(fields or {})),"excluded":excluded or []}

class SectionAnalysisTests(unittest.TestCase):
    def run_case(self,document,replies):
        t=Mock(side_effect=[response(x) for x in replies])
        return SectionAnalyzer("synthetic-key",transport=t),t
    def test_all_sections_project_to_original_offsets(self):
        doc="# Name\nAlpha\n# Features\ncheckout"
        a,t=self.run_case(doc,[extraction("S0001",fact("project_name","Alpha")),extraction("S0002",fact("features","checkout","user_action")),selection({"project_name":["F0001"],"features":["F0002"]}),verdict()])
        r=a.analyze(doc,"doc")
        self.assertEqual(r.provider_calls,4)
        self.assertEqual(r.profile["data"]["features"],["checkout"])
        span=r.profile["evidence"]["features"][0]
        self.assertEqual(doc[span["start"]:span["end"]],"checkout")
        self.assertEqual(r.diagnostics["sections_covered"],2)
    def test_missing_section_stops_without_partial_result(self):
        a,t=self.run_case("Alpha",[{"sections":[]}])
        with self.assertRaises(AnalysisError) as c:a.analyze("Alpha","doc")
        self.assertEqual(c.exception.code,"SECTION_COVERAGE")
        self.assertEqual(t.call_count,1)
    def test_quote_cannot_borrow_other_section(self):
        doc="# A\nAlpha\n# B\ncheckout"
        a,t=self.run_case(doc,[extraction("S0001",fact("features","checkout","user_action"))])
        with self.assertRaises(AnalysisError) as c:a.analyze(doc,"doc")
        self.assertEqual(c.exception.code,"SECTION_CANDIDATE")
    def test_unknown_selected_id_and_unaccounted_fact_fail(self):
        for merged in [selection({"project_name":["F9999"]}),selection()]:
            a,t=self.run_case("Alpha",[extraction("S0001",fact("project_name","Alpha")),merged])
            with self.assertRaises(AnalysisError) as c:a.analyze("Alpha","doc")
            self.assertEqual(c.exception.code,"SECTION_MERGE")
    def test_conflicting_confirmed_scalars_cannot_pick_one(self):
        merged=selection({"database":["F0001"]},[{"id":"F0002","reason":"conflict"}])
        a,t=self.run_case("SQLite PostgreSQL",[extraction("S0001",fact("database","SQLite"),fact("database","PostgreSQL")),merged])
        with self.assertRaises(AnalysisError):a.analyze("SQLite PostgreSQL","doc")
    def test_semantic_repair_and_recheck_respect_six_call_limit(self):
        doc="# Name\nAlpha\n# Features\ncheckout"
        chosen=selection({"project_name":["F0001"],"features":["F0002"]})
        a,t=self.run_case(doc,[extraction("S0001",fact("project_name","Alpha")),extraction("S0002",fact("features","checkout","user_action")),chosen,verdict([issue("overbroad")]),chosen,verdict()])
        r=a.analyze(doc,"doc")
        self.assertEqual(r.provider_calls,6)
        self.assertFalse(r.first_pass_validated)
        self.assertTrue(r.semantic_reviewed)
    def test_capacity_fails_before_any_provider_call(self):
        a,t=self.run_case("x"*24001,[])
        with self.assertRaises(AnalysisError) as c:a.analyze("x"*24001,"doc")
        self.assertEqual(c.exception.code,"SECTION_LIMIT")
        self.assertEqual(t.call_count,0)

    def test_deadline_prevents_late_success(self):
        now=[0]
        replies=iter([extraction("S0001",fact("project_name","Alpha")),selection({"project_name":["F0001"]}),verdict()])
        def transport(*args):
            now[0]+=20
            return response(next(replies))
        a=SectionAnalyzer("synthetic-key",transport=transport,clock=lambda:now[0])
        with self.assertRaises(AnalysisError) as c:a.analyze("Alpha","doc")
        self.assertEqual(c.exception.code,"ANALYSIS_DEADLINE")
        self.assertEqual(c.exception.provider_calls,3)
    def test_comparison_flags_cannot_disable_required_section_review(self):
        with self.assertRaises(TypeError):
            SectionAnalyzer("synthetic-key",semantic_review=False)
    def test_repaired_success_stores_no_raw_responses(self):
        import tempfile,json
        from pathlib import Path
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        chosen=selection({"features":["F0001"]})
        replies=[extraction("S0001",fact("features","checkout","user_action")),chosen,verdict([issue("overbroad")]),chosen,verdict()]
        with tempfile.TemporaryDirectory() as directory:
            t=Mock(side_effect=[response(x) for x in replies])
            a=SectionAnalyzer("synthetic-key",transport=t,diagnostics_store=LocalDiagnosticsStore(Path(directory)))
            r=a.analyze("checkout","doc")
            saved=json.loads(next(Path(directory).glob("analysis-*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["failed_responses"],[])
            self.assertEqual(r.provider_calls,5)

    def test_absence_is_not_unknown(self):
        a,t=self.run_case("none",[extraction("S0001",fact("external_integrations",None,"named_service","absent")),selection({"external_integrations":["F0001"]}),verdict()])
        r=a.analyze("none","doc")
        self.assertEqual(r.profile["data"]["external_integrations"],[])
        self.assertIsNone(r.profile["data"]["database"])
    def test_other_product_example_and_wrong_role_cannot_be_selected(self):
        for f in [fact("features","checkout","development_task"),
                  fact("features","checkout","user_action",scope="other"),
                  fact("features","checkout","user_action",scope="example"),
                  fact("features","checkout","user_action",status="tentative")]:
            a,t=self.run_case("checkout",[extraction("S0001",f),selection({"features":["F0001"]})])
            with self.subTest(f=f),self.assertRaises(AnalysisError) as c:a.analyze("checkout","doc")
            self.assertEqual(c.exception.code,"SECTION_MERGE")
    def test_duplicate_section_results_are_rejected(self):
        from agentfit_ai.section_analysis import validate_candidates
        from agentfit_ai.sections import split_sections
        batch=split_sections("# A\na\n# B\nb")
        reply={"sections":[{"sectionId":"S0001","facts":[]},{"sectionId":"S0001","facts":[]}]}
        with self.assertRaises(AnalysisError) as c:validate_candidates(reply,batch,0)
        self.assertEqual(c.exception.code,"SECTION_COVERAGE")
    def test_absence_and_presence_conflict_is_rejected(self):
        a,t=self.run_case("none GitHub",[extraction("S0001",fact("external_integrations",None,"named_service","absent"),fact("external_integrations","GitHub","named_service")),
            selection({"external_integrations":["F0001"]},[{"id":"F0002","reason":"conflict"}])])
        with self.assertRaises(AnalysisError) as c:a.analyze("none GitHub","doc")
        self.assertEqual(c.exception.code,"SECTION_MERGE")
