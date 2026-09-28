import unittest
from unittest.mock import Mock

from agentfit_ai.recoverable_analysis import RecoverableAnchoredAnalyzer
from test_semantic_review import verdict, issue
from test_staged_analysis import response


def candidates(*quotes):
    return {"units": [{"unitId": "U0001", "quotes": list(quotes)}]}


def chosen(field, role="product_fact", status="confirmed", decision="selected"):
    return {"field": field, "role": role, "status": status,
            "scope": "current", "decision": decision}


class RecoverableAnalysisTests(unittest.TestCase):
    def analyzer(self, replies):
        transport = Mock(side_effect=[response(item) if isinstance(item, dict) else item
                                      for item in replies])
        return RecoverableAnchoredAnalyzer("synthetic-key", transport=transport), transport

    def test_success_is_complete_with_existing_profile(self):
        analyzer, transport = self.analyzer([candidates("Alpha"),
            {"decisions": {"F0001": chosen("project_name")}}, verdict()])
        result = analyzer.analyze_recoverable("Alpha", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(transport.call_count, 3)

    def test_review_issue_success_requires_confirmation_when_opted_in(self):
        first = {"F0001": chosen("project_name"),
                 "F0002": chosen("features", "user_action")}
        repaired = {"F0001": chosen("project_name"),
                    "F0002": {"decision": "irrelevant"}}
        replies = [candidates("Alpha", "checkout"), {"decisions": first},
                   verdict([issue("overbroad")]), {"decisions": repaired},
                   verdict()]
        transport = Mock(side_effect=[response(item) for item in replies])
        analyzer = RecoverableAnchoredAnalyzer(
            "synthetic-key", transport=transport, require_issue_free_review=True)
        result = analyzer.analyze_recoverable("Alpha checkout", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(result["fieldStates"]["project_name"], "suggested")
        self.assertEqual(result["fieldStates"]["features"], "unknown")
        self.assertEqual(result["questions"], [])
        self.assertEqual(result["error"], "REVIEW_CONFIRMATION_REQUIRED")
        self.assertEqual(transport.call_count, 5)

    def test_default_still_completes_after_resolved_review_issue(self):
        first = {"F0001": chosen("project_name"),
                 "F0002": chosen("features", "user_action")}
        repaired = {"F0001": chosen("project_name"),
                    "F0002": {"decision": "irrelevant"}}
        analyzer, _ = self.analyzer([
            candidates("Alpha", "checkout"), {"decisions": first},
            verdict([issue("overbroad")]), {"decisions": repaired},
            verdict()])
        self.assertEqual(analyzer.analyze_recoverable("Alpha checkout", "doc")["outcome"],
                         "complete")

    def test_review_issue_gate_state_does_not_leak_to_next_call(self):
        first = {"F0001": chosen("project_name"),
                 "F0002": chosen("features", "user_action")}
        repaired = {"F0001": chosen("project_name"),
                    "F0002": {"decision": "irrelevant"}}
        replies = [candidates("Alpha", "checkout"), {"decisions": first},
                   verdict([issue("overbroad")]), {"decisions": repaired},
                   verdict(), candidates("Beta"),
                   {"decisions": {"F0001": chosen("project_name")}}, verdict()]
        transport = Mock(side_effect=[response(item) for item in replies])
        analyzer = RecoverableAnchoredAnalyzer(
            "synthetic-key", transport=transport, require_issue_free_review=True)
        self.assertEqual(analyzer.analyze_recoverable("Alpha checkout", "first")["outcome"],
                         "needs_confirmation")
        self.assertEqual(analyzer.analyze_recoverable("Beta", "second")["outcome"],
                         "complete")
        self.assertEqual(transport.call_count, 8)

    def test_candidate_failure_has_no_reusable_draft(self):
        analyzer, transport = self.analyzer([candidates("missing")])
        result = analyzer.analyze_recoverable("Alpha", "doc")
        self.assertEqual(result["outcome"], "failed")
        self.assertNotIn("profile", result)
        self.assertEqual(transport.call_count, 1)

    def test_all_unknown_profile_is_not_a_recoverable_draft(self):
        analyzer, transport = self.analyzer([candidates(),
            {"checkedFields": [], "issues": []}])
        result = analyzer.analyze_recoverable("Alpha", "doc")
        self.assertEqual(result, {"outcome": "failed", "error": "SEMANTIC_REVIEW_INVALID"})
        self.assertEqual(transport.call_count, 2)

    def test_judgment_failure_keeps_only_valid_independent_field(self):
        judgment = {"decisions": {"F0001": chosen("project_name"),
                                  "F0002": chosen("ai", "operating_model", "tentative")}}
        analyzer, transport = self.analyzer([candidates("Alpha", "Solar"), judgment])
        result = analyzer.analyze_recoverable("Alpha Solar", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertIsNone(result["profile"]["data"]["ai"])
        self.assertEqual(result["fieldStates"]["ai"], "unresolved")
        self.assertEqual(result["fieldStates"]["project_name"], "suggested")
        self.assertEqual(result["error"], "SECTION_MERGE")
        self.assertEqual(transport.call_count, 2)

    def test_missing_candidate_marks_reviewed_field_unresolved(self):
        missing = {"field": "database", "kind": "missing", "itemIndex": None,
                   "evidenceLineIds": [2]}
        analyzer, _ = self.analyzer([candidates("Alpha"),
            {"decisions": {"F0001": chosen("project_name")}}, verdict([missing])])
        result = analyzer.analyze_recoverable("Alpha\nSQLite", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["fieldStates"]["database"], "unresolved")
        self.assertEqual(result["fieldStates"]["project_name"], "suggested")
        self.assertEqual(result["fieldStates"]["ai"], "unknown")
        self.assertEqual(result["questions"][0]["field"], "database")

    def test_repeated_review_issue_discards_flagged_suggestion(self):
        first = {"F0001": chosen("project_name"),
                 "F0002": chosen("features", "user_action")}
        analyzer, transport = self.analyzer([
            candidates("Alpha", "checkout"), {"decisions": first},
            verdict([issue("overbroad")]), {"decisions": first},
            verdict([issue("overbroad")])])
        result = analyzer.analyze_recoverable("Alpha checkout", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertIsNone(result["profile"]["data"]["features"])
        self.assertEqual(result["fieldStates"]["features"], "unresolved")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(transport.call_count, 5)

    def test_review_rejection_of_only_suggestion_is_failed(self):
        selected = {"F0001": chosen("features", "user_action")}
        analyzer, transport = self.analyzer([
            candidates("checkout"), {"decisions": selected},
            verdict([issue("overbroad")]), {"decisions": selected},
            verdict([issue("overbroad")])])
        result = analyzer.analyze_recoverable("checkout", "doc")
        self.assertEqual(result, {"outcome": "failed", "error": "SEMANTIC_REJECTED"})
        self.assertEqual(transport.call_count, 5)

    def test_invalid_review_and_timeout_are_unreviewed(self):
        for review in ({"checkedFields": [], "issues": []}, TimeoutError()):
            with self.subTest(review=review):
                analyzer, transport = self.analyzer([candidates("Alpha"),
                    {"decisions": {"F0001": chosen("project_name")}}, review])
                result = analyzer.analyze_recoverable("Alpha", "doc")
                self.assertEqual(result["outcome"], "needs_confirmation")
                self.assertEqual(result["fieldStates"]["project_name"], "suggested")
                self.assertEqual(result["fieldStates"]["ai"], "unresolved")
                self.assertEqual(transport.call_count, 3)

    def test_pre_draft_failure_and_next_call_do_not_leak_state(self):
        analyzer, transport = self.analyzer([
            candidates("missing"), candidates("Alpha"),
            {"decisions": {"F0001": chosen("project_name")}}, verdict()])
        self.assertEqual(analyzer.analyze_recoverable("Alpha", "one")["outcome"], "failed")
        self.assertEqual(analyzer.analyze_recoverable("Alpha", "two")["outcome"], "complete")
        self.assertEqual(transport.call_count, 4)

    def test_sensitive_input_fails_before_network(self):
        analyzer, transport = self.analyzer([])
        result = analyzer.analyze_recoverable("synthetic-key", "doc")
        self.assertEqual(result, {"outcome": "failed", "error": "SENSITIVE_CONTENT"})
        transport.assert_not_called()

    def test_timeout_before_any_valid_candidate_has_no_draft(self):
        analyzer, transport = self.analyzer([TimeoutError()])
        result = analyzer.analyze_recoverable("Alpha", "doc")
        self.assertEqual(result, {"outcome": "failed", "error": "PROVIDER_TIMEOUT"})
        self.assertEqual(transport.call_count, 1)


if __name__ == "__main__":
    unittest.main()
