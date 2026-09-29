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
