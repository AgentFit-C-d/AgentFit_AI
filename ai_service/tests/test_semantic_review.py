import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import SolarAnalyzer, AnalysisError, cited_to_profile
from agentfit_ai.semantic_review import validate_review, ReviewValidationError
from agentfit_ai.diagnostics import LocalDiagnosticsStore
from test_staged_analysis import response, core, features

def verdict(issues=None):
    return {"checkedFields": list(FIELDS), "issues": issues or []}

def issue(kind="wrong_role", field="features", index=0):
    return {"field":field,"kind":kind,"itemIndex":index,"evidenceLineIds":[1]}

class ReviewContractTests(unittest.TestCase):
    def setUp(self):
        self.profile=cited_to_profile("Alpha registration","doc",dict(core(),**features()))
    def test_complete_check_accepts(self):
        self.assertEqual(validate_review(verdict(),self.profile,1),[])
    def test_missing_can_reference_null_field(self):
        value=verdict([issue("missing","database",None)])
        self.assertEqual(validate_review(value,self.profile,1),value["issues"])
    def test_invalid_coverage_extra_keys_ids_types_and_index_rejected(self):
        cases=[
            {"checkedFields":[],"issues":[]},
            dict(verdict(),extra="ignore validation"),
            verdict([dict(issue(),field="arbitrary")]),
            verdict([dict(issue(),kind="approve_everything")]),
            verdict([dict(issue(),evidenceLineIds=[2])]),
            verdict([dict(issue(),evidenceLineIds=[True])]),
            verdict([dict(issue(),itemIndex=True)]),
            verdict([dict(issue(),itemIndex=99)]),
            verdict([dict(issue(),itemIndex=None)]),
            verdict([dict(issue("missing"),itemIndex=0)]),
            verdict([dict(issue(field="database",index=None))]),
            verdict([dict(issue(),evidenceLineIds=[])]),
        ]
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ReviewValidationError):
                validate_review(value,self.profile,1)
    def test_duplicate_coverage_is_rejected(self):
        value=verdict()
        value["checkedFields"][-1]=value["checkedFields"][0]
        with self.assertRaises(ReviewValidationError):validate_review(value,self.profile,1)

class SemanticPipelineTests(unittest.TestCase):
    def run_case(self,replies,**kwargs):
        transport=Mock(side_effect=[response(x) if isinstance(x,dict) else x for x in replies])
        analyzer=SolarAnalyzer("synthetic-key", evidence_contract=False,transport=transport,**kwargs)
        return analyzer,transport

    def test_default_requires_review_and_sums_usage(self):
        analyzer,transport=self.run_case([core(),features(),verdict()])
        result=analyzer.analyze("Alpha registration","doc")
        self.assertEqual(result.provider_calls,3)
        self.assertTrue(result.semantic_reviewed)
        self.assertTrue(result.first_pass_validated)
        self.assertEqual(result.prompt_tokens,30)
        self.assertEqual(result.completion_tokens,60)
        self.assertEqual([c["stage"] for c in result.diagnostics["calls"]],["core","features","semantic_review"])
        payload=transport.call_args_list[2].args[0]
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]["required"],["checkedFields","issues"])
        self.assertIn("Alpha registration",payload["messages"][1]["content"])
        self.assertEqual(payload["reasoning_effort"],"medium")
        self.assertEqual(payload["max_tokens"],8192)
        self.assertEqual(transport.call_args_list[0].args[0]["reasoning_effort"],"none")
        self.assertEqual(result.diagnostics["calls"][2]["reasoning_effort"],"medium")

    def test_wrong_role_repaired_then_reviewed_again(self):
        analyzer,transport=self.run_case([core(),features(),verdict([issue()]),{"features":None},verdict()])
        result=analyzer.analyze("Alpha registration","doc")
        self.assertEqual(result.provider_calls,5)
        self.assertIsNone(result.profile["data"]["features"])
        self.assertFalse(result.first_pass_validated)
        self.assertEqual(result.repaired_fields,("features",))
        payload=transport.call_args_list[3].args[0]
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]["required"],["features"])
        self.assertEqual(result.profile["data"]["project_name"],"Alpha")

    def test_structural_and_semantic_repairs_never_exceed_six(self):
        analyzer,transport=self.run_case([core(),features(0),features(),verdict([issue()]),{"features":None},verdict()])
        result=analyzer.analyze("Alpha registration","doc")
        self.assertEqual(result.provider_calls,6)
        self.assertTrue(result.semantic_reviewed)

    def test_null_does_not_hide_missing_fact(self):
        analyzer,transport=self.run_case([core(),features(),verdict([issue()]),{"features":None},verdict([issue("missing",index=None)])])
        with self.assertRaises(AnalysisError) as caught:analyzer.analyze("Alpha registration","doc")
        self.assertEqual(caught.exception.code,"SEMANTIC_REJECTED")
        self.assertEqual(caught.exception.provider_calls,5)
        self.assertEqual(transport.call_count,5)

    def test_malformed_review_fails_without_repair(self):
        analyzer,transport=self.run_case([core(),features(),{"checkedFields":[],"issues":[]}])
        with self.assertRaises(AnalysisError) as caught:analyzer.analyze("Alpha registration","doc")
        self.assertEqual(caught.exception.code,"SEMANTIC_REVIEW_INVALID")
        self.assertEqual(transport.call_count,3)

    def test_repair_is_structurally_checked_before_rechecking(self):
        analyzer,transport=self.run_case([core(),features(),verdict([issue()]),features(99)])
        with self.assertRaises(AnalysisError):analyzer.analyze("Alpha registration","doc")
        self.assertEqual(transport.call_count,4)

    def test_review_network_failure_is_not_retried(self):
        analyzer,transport=self.run_case([core(),features(),TimeoutError()])
        with self.assertRaises(AnalysisError) as caught:analyzer.analyze("Alpha registration","doc")
        self.assertEqual(caught.exception.code,"PROVIDER_TIMEOUT")
        self.assertEqual(caught.exception.diagnostics["calls"][-1]["stage"],"semantic_review")
        self.assertEqual(transport.call_count,3)

    def test_explicit_baseline_is_marked_unreviewed(self):
        analyzer,_=self.run_case([core(),features()],semantic_review=False)
        result=analyzer.analyze("Alpha registration","doc")
        self.assertFalse(result.semantic_reviewed)
        self.assertFalse(result.diagnostics["semantic_review_enabled"])

    def test_deadline_rejects_late_response_and_limits_transport_timeout(self):
        now=[0.0];timeouts=[];replies=iter([core(),features(),verdict()])
        def transport(payload,key,timeout):
            timeouts.append(timeout);now[0]+=20
            return response(next(replies))
        analyzer=SolarAnalyzer("synthetic-key", evidence_contract=False,transport=transport,clock=lambda:now[0])
        with self.assertRaises(AnalysisError) as caught:analyzer.analyze("Alpha registration","doc")
        self.assertEqual(caught.exception.code,"ANALYSIS_DEADLINE")
        self.assertEqual(timeouts,[40,40,20])

    def test_reviewed_repaired_success_keeps_no_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            analyzer,_=self.run_case([core(),features(),verdict([issue()]),{"features":None},verdict()],diagnostics_store=LocalDiagnosticsStore(Path(directory)))
            analyzer.analyze("Alpha registration","doc")
            record=json.loads(next(Path(directory).glob("analysis-*.json")).read_text())
            self.assertEqual(record["failed_responses"],[])

    def test_final_rejection_retains_only_failed_call_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            analyzer,_=self.run_case([core(),features(),verdict([issue()]),{"features":None},verdict([issue("missing",index=None)])],diagnostics_store=LocalDiagnosticsStore(Path(directory)))
            with self.assertRaises(AnalysisError):analyzer.analyze("Alpha registration","doc")
            record=json.loads(next(Path(directory).glob("analysis-*.json")).read_text())
            ids={x["call"] for x in record["failed_responses"]}
            self.assertIn(2,ids)
            self.assertIn(4,ids)
            self.assertNotIn(1,ids)

class SemanticErrorMetadataTests(unittest.TestCase):
    def test_final_rejection_reports_every_attempted_repair_field(self):
        rejected=verdict([issue()])
        transport=Mock(side_effect=[response(core()),response(features(0)),response(features()),
                                   response(rejected),response({"features":None}),
                                   response(verdict([issue("missing",index=None)]))])
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key", evidence_contract=False,transport=transport).analyze("Alpha registration","doc")
        self.assertEqual(caught.exception.provider_calls,6)
        self.assertEqual(caught.exception.repaired_fields,("features",))
        self.assertFalse(caught.exception.first_pass_validated)

    def test_review_timeout_after_repair_preserves_repair_metadata(self):
        transport=Mock(side_effect=[response(core()),response(features(0)),response(features()),TimeoutError()])
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key", evidence_contract=False,transport=transport).analyze("Alpha registration","doc")
        self.assertEqual(caught.exception.repaired_fields,("features",))


class ReviewTimeBudgetTests(unittest.TestCase):
    def test_review_can_use_remaining_budget_beyond_extraction_cap(self):
        now=[0.0];timeouts=[];replies=iter([core(),features(),verdict()])
        def transport(payload,key,timeout):
            timeouts.append(timeout)
            now[0] += 5
            return response(next(replies))
        result=SolarAnalyzer("synthetic-key", evidence_contract=False,transport=transport,clock=lambda:now[0]).analyze("Alpha registration","doc")
        self.assertEqual(timeouts,[40,40,50])
        self.assertTrue(result.semantic_reviewed)
