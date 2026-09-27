import unittest

from agentfit_ai.keyed_profile_evaluation import focus_score, full_score, summarize, validation_error_count
from agentfit_ai.profile import FIELDS


class KeyedProfileEvaluationTests(unittest.TestCase):
    def test_wrong_absence_is_not_a_pure_omission(self):
        profile = {"data": dict.fromkeys(FIELDS), "sources": dict.fromkeys(FIELDS)}
        profile["data"]["external_integrations"] = ["WrongService"]
        profile["sources"]["external_integrations"] = "DOCUMENT"
        self.assertEqual(full_score(profile, {"external_integrations": []})["false_confirmations"], 1)

    def test_validation_errors_are_separate_from_provider_timeouts(self):
        self.assertEqual(validation_error_count({"errors": {
            "PROVIDER_TIMEOUT": 3, "ANCHORED_CANDIDATE": 2}}), 2)

    def test_focus_requires_field_value_and_source_position(self):
        case = {"document": "현재 서버는 Ktor다. 과거 서버는 Flask다.",
                "sections": ["현재 서버는 Ktor다. 과거 서버는 Flask다."],
                "gold": [{"section": 0, "field": "backend", "quote": "Ktor"}],
                "forbidden": ["Flask"]}
        start = case["document"].index("Ktor")
        profile = {"data": {"backend": ["Ktor"]},
                   "evidence": {"backend": [{"start": start, "end": start + 4}]}}
        self.assertEqual(focus_score(case, profile)["matched"], 1)
        profile["evidence"]["backend"] = [{"start": 28, "end": 33}]
        self.assertEqual(focus_score(case, profile)["matched"], 0)
        profile["data"]["backend"] = ["Ktor", "Flask"]
        self.assertEqual(focus_score(case, profile)["false_confirmations"], 1)

    def test_summary_counts_errors_without_calling_them_correct(self):
        rows = [{"gold_total": 2, "baseline": {"error": "ANCHORED_CANDIDATE", "provider_calls": 2, "elapsed_ms": 12},
                 "new": {"passed": True, "matched": 2, "total": 2,
                         "false_confirmations": 0, "provider_calls": 4, "elapsed_ms": 15}}]
        summary = summarize(rows, "new")
        self.assertEqual(summary["valid"], 1)
        self.assertEqual(summary["matched"], 2)
        self.assertEqual(summary["total_planned"], 2)
        self.assertEqual(summary["max_calls"], 4)
        self.assertEqual(summarize(rows, "baseline")["valid"], 0)
        self.assertEqual(summarize(rows, "baseline")["total_planned"], 2)
