import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from agentfit_ai.recoverable_solar_analysis import RecoverableSolarAnalyzer
from agentfit_ai.profile import FIELDS
from test_staged_analysis import response, core, features
from test_semantic_review import verdict, issue
from test_evidence_contract import fact, confirmed


class RecoverableSolarAnalysisTests(unittest.TestCase):
    def analyzer(self, replies):
        transport = Mock(side_effect=[response(item) if type(item) is dict else item
                                      for item in replies])
        return RecoverableSolarAnalyzer("synthetic-key", evidence_contract=False,
                                        transport=transport), transport

    def test_review_timeout_retains_verified_suggestions_with_questions(self):
        analyzer, transport = self.analyzer([core(), features(), TimeoutError("private failure")])
        result = analyzer.analyze_recoverable("Alpha registration", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "PROVIDER_TIMEOUT")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(result["fieldStates"]["project_name"], "suggested")
        self.assertIn({"field": "project_name", "reason": "REVIEW_UNAVAILABLE",
                       "questionId": "confirm_project_name"}, result["questions"])
        self.assertEqual([question["field"] for question in result["questions"]],
                         ["project_name", "features"])
        self.assertEqual(result["fieldStates"]["database"], "unknown")
        self.assertEqual(transport.call_count, 3)
        self.assertNotIn("private failure", json.dumps(result))
        self.assertNotIn("synthetic-key", json.dumps(result))

    def test_review_issue_field_is_cleared_if_repair_fails(self):
        analyzer, _ = self.analyzer([core(), features(), verdict([issue()]),
                                     TimeoutError("private failure")])
        result = analyzer.analyze_recoverable("Alpha registration", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertIsNone(result["profile"]["data"]["features"])
        self.assertEqual(result["fieldStates"]["features"], "unresolved")
        self.assertIn({"field": "features", "reason": "REVIEW_ISSUE",
                       "questionId": "confirm_features"}, result["questions"])
        self.assertEqual(result["fieldStates"]["project_name"], "suggested")

    def test_failure_before_verified_profile_stays_failed(self):
        analyzer, _ = self.analyzer([TimeoutError("private failure")])
        self.assertEqual(analyzer.analyze_recoverable("Alpha registration", "doc"),
                         {"outcome": "failed", "error": "PROVIDER_TIMEOUT"})

    def evidence_replies(self, *, valid_other_fields=True, repair_timeout=False):
        initial = {field: None for field in FIELDS if field != "features"}
        initial["project_name"] = confirmed(fact("private-marker"))
        if valid_other_fields:
            initial["domain"] = confirmed(fact("Finance"))
        feature_reply = {"features": confirmed(fact("checkout", role="user_action"))
                         if valid_other_fields else None}
        repair = (TimeoutError("private provider text") if repair_timeout else
                  response({"project_name": confirmed(fact("private-marker"))}))
        transport = Mock(side_effect=[response(initial), response(feature_reply), repair])
        analyzer = RecoverableSolarAnalyzer("synthetic-key", evidence_contract=True,
                                            transport=transport)
        return analyzer, transport

    def test_invalid_name_after_repair_keeps_other_fields_as_unreviewed_draft(self):
        analyzer, transport = self.evidence_replies()
        result = analyzer.analyze_recoverable("Finance checkout", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertIsNone(result["profile"]["data"]["project_name"])
        self.assertEqual(result["fieldStates"]["project_name"], "unresolved")
        self.assertEqual(result["profile"]["data"]["domain"], "Finance")
        self.assertEqual(result["profile"]["data"]["features"], ["checkout"])
        self.assertIn({"field": "project_name", "reason": "ANALYSIS_UNRESOLVED",
                       "questionId": "confirm_project_name"}, result["questions"])
        self.assertIn({"field": "domain", "reason": "REVIEW_UNAVAILABLE",
                       "questionId": "confirm_domain"}, result["questions"])
        self.assertEqual(transport.call_count, 3)
        self.assertNotIn("private-marker", json.dumps(result))

    def test_repair_timeout_keeps_only_earlier_verified_fields(self):
        analyzer, _ = self.evidence_replies(repair_timeout=True)
        result = analyzer.analyze_recoverable("Finance checkout", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "PROVIDER_TIMEOUT")
        self.assertEqual(result["fieldStates"]["project_name"], "unresolved")
        self.assertEqual(result["fieldStates"]["domain"], "suggested")

    def test_no_valid_non_null_field_remains_failed(self):
        analyzer, _ = self.evidence_replies(valid_other_fields=False)
        self.assertEqual(analyzer.analyze_recoverable("Finance checkout", "doc"),
                         {"outcome": "failed", "error": "INVALID_EVIDENCE"})

    def test_review_issues_removing_all_values_leave_no_draft(self):
        analyzer, _ = self.analyzer([
            core(), features(),
            verdict([issue("unsupported", "project_name", None),
                     issue("wrong_role", "features", 0)]),
            TimeoutError("private failure")])
        self.assertEqual(analyzer.analyze_recoverable("Alpha registration", "doc"),
                         {"outcome": "failed", "error": "PROVIDER_TIMEOUT"})

    def test_complete_success_keeps_existing_profile(self):
        analyzer, _ = self.analyzer([core(), features(), verdict()])
        outcome = analyzer.analyze_recoverable("Alpha registration", "doc")
        self.assertEqual(outcome["outcome"], "complete")
        self.assertEqual(outcome["profile"]["data"]["project_name"], "Alpha")
        self.assertNotIn("questions", outcome)

    def test_concurrent_requests_keep_their_own_verified_drafts(self):
        local = threading.local()
        overlap = threading.Barrier(2, timeout=5)

        def transport(*_):
            local.calls += 1
            if local.calls == 1:
                fields = core()
                fields["project_name"]["value"] = local.name
                return response(fields)
            if local.calls == 2:
                return response(features())
            overlap.wait()
            raise TimeoutError("private failure")

        analyzer = RecoverableSolarAnalyzer("synthetic-key", evidence_contract=False,
                                            transport=transport)

        def run(name):
            local.name = name
            local.calls = 0
            return analyzer.analyze_recoverable(name + " registration", name)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, ("Alpha", "Beta")))
        self.assertEqual([result["outcome"] for result in results],
                         ["needs_confirmation", "needs_confirmation"])
        self.assertEqual([result["profile"]["data"]["project_name"] for result in results],
                         ["Alpha", "Beta"])


if __name__ == "__main__":
    unittest.main()
