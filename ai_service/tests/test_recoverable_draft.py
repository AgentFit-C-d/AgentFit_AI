import json
import unittest

from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.recoverable_draft import project_draft


DOCUMENT = "Raven project. No external integrations. PRIVATE_SOURCE_MARKER"


def profile():
    data = dict.fromkeys(FIELDS)
    data["project_name"] = "Raven"
    data["external_integrations"] = []
    evidence = {field: [] for field in FIELDS}
    evidence["project_name"] = [{"start": 0, "end": 5}]
    start = DOCUMENT.index("No external integrations")
    evidence["external_integrations"] = [{"start": start,
                                          "end": start + len("No external integrations")}]
    return validate_profile(DOCUMENT, "doc", {"data": data, "evidence": evidence})


class RecoverableDraftTests(unittest.TestCase):
    def test_unresolved_value_is_cleared_but_explicit_absence_keeps_evidence(self):
        result = project_draft(DOCUMENT, "doc", profile(),
                               unresolved={"project_name": "REVIEW_ISSUE"},
                               review_complete=True, error_code="SEMANTIC_REJECTED")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["profile"]["data"]["project_name"], None)
        self.assertEqual(result["profile"]["evidence"]["project_name"], [])
        self.assertEqual(result["fieldStates"]["project_name"], "unresolved")
        self.assertEqual(result["fieldStates"]["database"], "unknown")
        self.assertEqual(result["profile"]["data"]["external_integrations"], [])
        self.assertEqual(result["fieldStates"]["external_integrations"], "suggested")
        self.assertEqual(result["questions"], [{"field": "project_name",
                                                 "reason": "REVIEW_ISSUE",
                                                 "questionId": "confirm_project_name"}])

    def test_unreviewed_nulls_need_confirmation_and_no_source_is_copied(self):
        result = project_draft(DOCUMENT, "doc", profile(), unresolved={},
                               review_complete=False, error_code="PROVIDER_TIMEOUT")
        self.assertEqual(result["fieldStates"]["project_name"], "suggested")
        self.assertEqual(result["fieldStates"]["database"], "unresolved")
        self.assertEqual(len(result["questions"]), 8)
        self.assertNotIn("PRIVATE_SOURCE_MARKER", json.dumps(result))
        self.assertEqual(result["error"], "PROVIDER_TIMEOUT")

    def test_unreviewed_suggestions_can_require_explicit_confirmation(self):
        result = project_draft(DOCUMENT, "doc", profile(), unresolved={},
                               review_complete=False, error_code="PROVIDER_TIMEOUT",
                               ask_suggested_when_unreviewed=True)
        self.assertEqual(result["fieldStates"]["project_name"], "suggested")
        self.assertEqual(result["profile"]["data"]["project_name"], "Raven")
        self.assertEqual(len(result["questions"]), len(FIELDS))
        self.assertIn({"field": "project_name", "reason": "REVIEW_UNAVAILABLE",
                       "questionId": "confirm_project_name"}, result["questions"])
        self.assertNotIn("PRIVATE_SOURCE_MARKER", json.dumps(result))

    def test_reviewed_suggestions_can_require_explicit_confirmation(self):
        result = project_draft(
            DOCUMENT, "doc", profile(),
            unresolved={"project_name": "REVIEW_ISSUE"},
            review_complete=True, error_code="SEMANTIC_REJECTED",
            ask_suggested_when_reviewed=True)
        self.assertEqual(result["fieldStates"]["external_integrations"], "suggested")
        self.assertIn({"field": "external_integrations",
                       "reason": "CONFIRM_SUGGESTION",
                       "questionId": "confirm_external_integrations"},
                      result["questions"])
        self.assertIn({"field": "project_name", "reason": "REVIEW_ISSUE",
                       "questionId": "confirm_project_name"}, result["questions"])

    def test_unreviewed_unknowns_can_remain_editable_without_blanket_questions(self):
        result = project_draft(DOCUMENT, "doc", profile(), unresolved={},
                               review_complete=False, error_code="PROVIDER_TIMEOUT",
                               ask_suggested_when_unreviewed=True,
                               ask_unknown_when_unreviewed=False)
        self.assertEqual(result["fieldStates"]["database"], "unknown")
        self.assertEqual([question["field"] for question in result["questions"]],
                         ["project_name", "external_integrations"])

    def test_provider_text_is_not_returned_as_reason_or_error(self):
        result = project_draft(DOCUMENT, "doc", profile(),
                               unresolved={"ai": "PRIVATE_PROVIDER_TEXT"},
                               review_complete=True, error_code="PRIVATE_PROVIDER_TEXT")
        self.assertNotIn("PRIVATE_PROVIDER_TEXT", json.dumps(result))
        self.assertEqual(result["error"], "ANALYSIS_FAILURE")
        self.assertEqual(result["questions"], [{"field": "ai",
                                                 "reason": "ANALYSIS_UNRESOLVED",
                                                 "questionId": "confirm_ai"}])


if __name__ == "__main__":
    unittest.main()
