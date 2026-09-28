import json
import tempfile
import unittest
from pathlib import Path

from agentfit_ai.profile import FIELDS, validate_profile

try:
    from agentfit_ai.false_complete_evaluation import aggregate, run_case, write_safe_json
except ImportError:
    aggregate = run_case = write_safe_json = None


def named_profile(document, value, start):
    data = dict.fromkeys(FIELDS)
    data["project_name"] = value
    evidence = {field: [] for field in FIELDS}
    evidence["project_name"] = [{"start": start, "end": start + len(value)}]
    return validate_profile(document, "T01", {"data": data, "evidence": evidence})


class FalseCompleteEvaluationTests(unittest.TestCase):
    def test_one_analysis_and_safe_false_complete_row(self):
        self.assertIsNotNone(run_case)
        case = {"id": "T01", "kind": "full", "document": "Atlas Beta",
                "gold": {"project_name": "Atlas"}}
        wrong = named_profile(case["document"], "Beta", 6)
        calls = []

        class FakeAnalyzer:
            def __init__(self, key, *, transport, **kwargs):
                self.transport = transport

            def analyze_observed(self, document, document_id):
                calls.append((document, document_id))
                self.transport({}, "test-key", 1)
                return ({"outcome": "complete", "profile": wrong},
                        {"candidates": [{"id": "F0001", "start": 6, "end": 10}],
                         "profiles": [("judgment", wrong)],
                         "reviews": [("semantic_review", [])]})

        row = run_case(case, "test-key", provider=lambda *args: b"private-response",
                       analyzer_factory=FakeAnalyzer)
        self.assertEqual(calls, [("Atlas Beta", "T01")])
        self.assertEqual(row["provider_calls"], 1)
        self.assertEqual(row["analysis_runs"], 1)
        self.assertEqual(row["outcome"], "complete")
        self.assertEqual(row["false_confirmations"], 1)
        self.assertEqual(row["candidate_spans"], [{"id": "F0001", "start": 6, "end": 10}])
        self.assertEqual(row["false_complete_fields"][0]["field"], "project_name")
        self.assertNotIn("Atlas Beta", json.dumps(row))
        self.assertNotIn("Beta", json.dumps(row))
        self.assertNotIn("test-key", json.dumps(row))
        self.assertNotIn("private-response", json.dumps(row))

    def test_non_complete_outcomes_are_not_false_confirmations(self):
        self.assertIsNotNone(run_case)
        case = {"id": "T01", "kind": "full", "document": "Atlas Beta",
                "gold": {"project_name": "Atlas"}}
        draft = named_profile(case["document"], "Beta", 6)

        class FakeAnalyzer:
            def __init__(self, key, *, transport, **kwargs):
                pass

            def analyze_observed(self, document, document_id):
                return ({"outcome": "needs_confirmation", "profile": draft,
                         "fieldStates": {field: "suggested" for field in FIELDS},
                         "questions": [], "error": "PROVIDER_TIMEOUT"},
                        {"candidates": [], "profiles": [("judgment", draft)],
                         "reviews": []})

        row = run_case(case, "test-key", analyzer_factory=FakeAnalyzer)
        self.assertEqual(row["outcome"], "needs_confirmation")
        self.assertEqual(row["false_confirmations"], 0)
        self.assertEqual(row["false_complete_fields"], [])

    def test_review_issue_confirmation_counts_prevented_wrong_value(self):
        case = {"id": "T01", "kind": "full", "document": "Atlas Beta",
                "gold": {"project_name": "Atlas"}}
        wrong = named_profile(case["document"], "Beta", 6)

        class FakeAnalyzer:
            def __init__(self, key, *, transport, **kwargs):
                pass

            def analyze_observed(self, document, document_id):
                return ({"outcome": "needs_confirmation", "profile": wrong,
                         "error": "REVIEW_CONFIRMATION_REQUIRED"},
                        {"candidates": [], "profiles": [], "reviews": []})

        row = run_case(case, "test-key", analyzer_factory=FakeAnalyzer)
        self.assertEqual(row["false_confirmations"], 0)
        self.assertTrue(row["review_issue_gate_applied"])
        self.assertEqual(row["gated_potential_false_confirmations"], 1)
        summary = aggregate([row], planned=1)
        self.assertEqual(summary["review_issue_confirmations"], 1)
        self.assertEqual(summary["gated_potential_false_confirmations"], 1)

    def test_invalid_complete_profile_is_unscored_not_zero_false_confirmations(self):
        case = {"id": "T01", "kind": "full", "document": "Atlas Beta",
                "gold": {"project_name": "Atlas"}}
        invalid = named_profile(case["document"], "Beta", 6)
        invalid["evidence"]["project_name"] = [{"start": 0, "end": 4}]

        class FakeAnalyzer:
            def __init__(self, key, *, transport, **kwargs):
                pass

            def analyze_observed(self, document, document_id):
                return ({"outcome": "complete", "profile": invalid},
                        {"candidates": [], "profiles": [], "reviews": []})

        row = run_case(case, "test-key", analyzer_factory=FakeAnalyzer)
        self.assertEqual(row["structural_evidence_errors"], 1)
        self.assertIsNone(row["false_confirmations"])
        self.assertEqual(row["scoring_status"], "unscored_invalid_profile")
        summary = aggregate([row], planned=1)
        self.assertEqual(summary["unscored_complete_cases"], 1)
        self.assertFalse(summary["gate"]["zero_wrong_auto_confirmations"])

    def test_subspan_mode_marks_stage_unavailable_instead_of_candidate_gap(self):
        case = {"id": "T01", "kind": "full", "document": "Atlas Beta",
                "gold": {"project_name": "Atlas"}}
        wrong = named_profile(case["document"], "Beta", 6)

        class FakeAnalyzer:
            def __init__(self, key, *, transport, **kwargs):
                pass

            def analyze_observed(self, document, document_id):
                return ({"outcome": "complete", "profile": wrong},
                        {"candidates": [{"id": "F0001", "start": 0, "end": 10}],
                         "profiles": [("judgment", wrong)], "reviews": []})

        row = run_case(case, "test-key", analyzer_factory=FakeAnalyzer,
                       diagnose_stages=False)
        self.assertEqual(row["false_confirmations"], 1)
        self.assertEqual(row["diagnostic_error"], "SUBSPAN_STAGE_UNSUPPORTED")
        self.assertEqual(row["false_complete_fields"][0]["first_observed_divergence"],
                         "undetermined")
        self.assertEqual(row["false_complete_fields"][0]["field"], "project_name")
        self.assertEqual(row["false_complete_fields"][0]["candidate_spans"],
                         [{"id": "F0001", "start": 0, "end": 10}])
        self.assertEqual(row["false_complete_fields"][0]["evidence_spans"],
                         [{"start": 6, "end": 10}])

    def test_failed_case_blocks_pass_even_when_other_limits_hold(self):
        row = {"outcome": "failed", "analysis_runs": 1, "provider_calls": 1,
               "elapsed_ms": 100, "false_confirmations": 0,
               "false_complete_fields": []}
        summary = aggregate([row], planned=1)
        self.assertEqual(summary["failed_cases"], 1)
        self.assertFalse(summary["gate"]["zero_failed_cases"])
        self.assertFalse(summary["passed"])

    def test_subspan_mode_keeps_each_false_field(self):
        document = "Atlas Beta Web Mobile"
        data = dict.fromkeys(FIELDS)
        data.update(project_name="Beta", project_type="Mobile")
        evidence = {field: [] for field in FIELDS}
        evidence["project_name"] = [{"start": 6, "end": 10}]
        evidence["project_type"] = [{"start": 15, "end": 21}]
        wrong = validate_profile(document, "T01", {"data": data, "evidence": evidence})
        case = {"id": "T01", "kind": "full", "document": document,
                "gold": {"project_name": "Atlas", "project_type": "Web"}}

        class FakeAnalyzer:
            def __init__(self, key, *, transport, **kwargs):
                pass

            def analyze_observed(self, document, document_id):
                return ({"outcome": "complete", "profile": wrong},
                        {"candidates": [], "profiles": [], "reviews": []})

        row = run_case(case, "test-key", analyzer_factory=FakeAnalyzer,
                       diagnose_stages=False)
        self.assertEqual(row["false_confirmations"], 2)
        self.assertEqual({item["field"] for item in row["false_complete_fields"]},
                         {"project_name", "project_type"})
        self.assertEqual({item["first_observed_divergence"]
                          for item in row["false_complete_fields"]}, {"undetermined"})

    def test_fixed_denominator_and_limits(self):
        self.assertIsNotNone(aggregate)
        rows = [
            {"outcome": "complete", "analysis_runs": 1, "provider_calls": 3,
             "elapsed_ms": 100, "false_confirmations": 1,
             "false_complete_fields": [{"first_observed_divergence": "judgment_mismatch",
                                        "review_detected": False}]},
            {"outcome": "needs_confirmation", "analysis_runs": 1,
             "provider_calls": 6, "elapsed_ms": 61000,
             "false_confirmations": 0, "false_complete_fields": []},
            {"outcome": "failed", "analysis_runs": 1, "provider_calls": 1,
             "elapsed_ms": 200, "false_confirmations": 0,
             "false_complete_fields": []},
        ]
        result = aggregate(rows, planned=3)
        self.assertEqual(result["evaluated_cases"], 3)
        self.assertEqual(result["complete_cases"], 1)
        self.assertEqual(result["needs_confirmation_cases"], 1)
        self.assertEqual(result["failed_cases"], 1)
        self.assertEqual(result["wrong_auto_confirmations"], 1)
        self.assertEqual(result["first_observed_divergence"]["judgment_mismatch"], 1)
        self.assertEqual(result["review_detected"]["false"], 1)
        self.assertEqual(result["observed_over_60s"], 1)
        self.assertFalse(result["gate"]["observed_60s_limit"])

    def test_writer_rejects_nested_source_without_creating_artifact(self):
        self.assertIsNotNone(write_safe_json)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "results.json"
            with self.assertRaises(ValueError):
                write_safe_json(path, {"rows": [{"diagnostic": {"raw": "private"}}]})
            self.assertFalse(path.exists())
            with self.assertRaises(ValueError):
                write_safe_json(path, {"rows": [{"id": "secret-source"}]},
                                forbidden_strings=["secret-source"])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
