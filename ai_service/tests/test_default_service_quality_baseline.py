import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agentfit_ai.default_service_quality_baseline import aggregate, run_case, write_report
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError


class DefaultServiceQualityBaselineTests(unittest.TestCase):
    def test_success_uses_worker_settings_and_scores_complete(self):
        seen = {}
        profile = {"data": dict.fromkeys(FIELDS), "sources": dict.fromkeys(FIELDS),
                   "evidence": {field: [] for field in FIELDS}}
        profile["data"]["ai"] = ["WrongModel"]
        profile["sources"]["ai"] = "DOCUMENT"

        class Analyzer:
            def __init__(self, key, **kwargs):
                seen.update(key=key, **kwargs)

            def analyze(self, document, case_id):
                self_result = SimpleNamespace(profile=profile, provider_calls=3, elapsed_ms=12)
                return self_result

        case = {"id": "CASE-1", "kind": "full", "document": "private source", "gold": {"ai": None}}
        row = run_case(case, "private-key", analyzer_factory=Analyzer, provider=lambda *_: b"")
        self.assertEqual(seen["model"], "solar-pro4")
        self.assertEqual(seen["analysis_timeout_seconds"], 40)
        self.assertTrue(seen["semantic_review"])
        self.assertTrue(seen["evidence_contract"])
        self.assertEqual(row["outcome"], "complete")
        self.assertEqual(row["false_confirmations"], 1)
        self.assertEqual(row["mismatch_fields"], ["ai"])
        self.assertEqual(row["provider_calls"], 3)
        self.assertNotIn("private source", json.dumps(row))

    def test_failure_is_not_scored_as_correct(self):
        class Analyzer:
            def __init__(self, key, **kwargs):
                pass

            def analyze(self, document, case_id):
                error = AnalysisError("SEMANTIC_REJECTED")
                error.provider_calls = 4
                raise error

        row = run_case({"id": "CASE-2", "kind": "full", "document": "private source",
                        "gold": {}}, "private-key", analyzer_factory=Analyzer,
                       provider=lambda *_: b"")
        self.assertEqual(row["outcome"], "failed")
        self.assertIsNone(row["false_confirmations"])
        summary = aggregate([row], planned=1)
        self.assertEqual(summary["failed_cases"], 1)
        self.assertFalse(summary["passed"])

    def test_completed_omission_cannot_pass_gate(self):
        row = {"outcome": "complete", "passed": False, "matched": 9,
               "gold_total": 10, "false_confirmations": 0,
               "provider_calls": 2, "elapsed_ms": 10, "error": None}
        self.assertFalse(aggregate([row], planned=1)["gate"]["all_complete_cases_correct"])

    def test_timeout_identifies_stage_without_leaking_diagnostic_payload(self):
        class Analyzer:
            def __init__(self, key, **kwargs):
                pass

            def analyze(self, document, case_id):
                error = AnalysisError("PROVIDER_TIMEOUT")
                error.diagnostics = {"calls": [
                    {"stage": "core", "outcome": "validated", "elapsed_ms": 8000,
                     "provider_elapsed_ms": 7900, "raw": "private source"},
                    {"stage": "semantic_review", "outcome": "failed", "elapsed_ms": 32000,
                     "provider_elapsed_ms": 32000, "error": "PROVIDER_TIMEOUT",
                     "validation_errors": [{"detail": "private source"}]},
                ]}
                raise error

        row = run_case({"id": "CASE-3", "kind": "full", "document": "private source",
                        "gold": {}}, "private-key", analyzer_factory=Analyzer,
                       provider=lambda *_: b"")
        self.assertEqual([call["stage"] for call in row["call_timings"]],
                         ["core", "semantic_review"])
        self.assertEqual(aggregate([row], planned=1)["timeout_stages"],
                         {"semantic_review": 1})
        self.assertNotIn("private source", json.dumps(row))

    def test_untrusted_stage_and_outcome_are_not_saved(self):
        from agentfit_ai.default_service_quality_baseline import project_call_timings
        calls = project_call_timings({"calls": [{
            "stage": "private source", "outcome": "private response",
            "elapsed_ms": -1, "provider_elapsed_ms": "private source"}]})
        self.assertEqual(calls, [])
        self.assertEqual(project_call_timings({"calls": [{
            "stage": {"private": "source"}, "outcome": ["private response"]}]}), [])

    def test_review_invalid_reason_is_allowlisted_and_counted(self):
        from agentfit_ai.default_service_quality_baseline import project_call_timings
        diagnostic = {"calls": [
            {"stage": "semantic_review", "outcome": "validation_failed", "elapsed_ms": 10,
             "review_error": {"reason": "CHECKED_FIELDS", "private": "private source"}},
            {"stage": "semantic_recheck", "outcome": "validation_failed", "elapsed_ms": 8,
             "review_error": {"reason": "private source"}},
        ]}
        calls = project_call_timings(diagnostic)
        self.assertEqual(calls[0]["review_invalid_reason"], "CHECKED_FIELDS")
        self.assertNotIn("review_invalid_reason", calls[1])
        self.assertNotIn("private source", json.dumps(calls))
        row = {"outcome": "failed", "passed": False, "matched": None,
               "gold_total": 10, "false_confirmations": None, "provider_calls": 2,
               "elapsed_ms": 18, "error": "SEMANTIC_REVIEW_INVALID", "call_timings": calls}
        self.assertEqual(aggregate([row], planned=1)["review_invalid_reasons"],
                         {"CHECKED_FIELDS": 1})

    def test_report_rejects_source_and_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with self.assertRaises(ValueError):
                write_report(output, {"document": "source"}, [], {}, forbidden=("source", "secret"))
            self.assertFalse(output.exists())
            write_report(output, {"cases": 1}, [{"id": "CASE-1", "outcome": "failed"}],
                         {"passed": False}, forbidden=("source", "secret"))
            self.assertEqual(json.loads((output / "summary.json").read_text())["passed"], False)


if __name__ == "__main__":
    unittest.main()
