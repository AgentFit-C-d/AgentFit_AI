import json
import tempfile
import unittest
from pathlib import Path

from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.recoverable_draft_evaluation import aggregate, run_case, write_json


def profile(document="Atlas"):
    data = dict.fromkeys(FIELDS)
    data["project_name"] = "Atlas"
    evidence = {field: [] for field in FIELDS}
    evidence["project_name"] = [{"start": 0, "end": 5}]
    return validate_profile(document, "doc", {"data": data, "evidence": evidence})


class RecoverableEvaluationTests(unittest.TestCase):
    def test_one_analysis_call_and_safe_result(self):
        case = {"id": "T01", "kind": "full", "document": "Atlas secret-source",
                "gold": {"project_name": "Atlas"}}
        calls = []
        class FakeAnalyzer:
            def __init__(self, key, *, transport, **kwargs):
                self.transport = transport
            def analyze_recoverable(self, document, document_id):
                calls.append((document, document_id))
                self.transport({}, "test-key", 1)
                return {"outcome": "needs_confirmation", "profile": profile(case["document"]),
                        "fieldStates": {f: "suggested" if f == "project_name" else "unresolved" for f in FIELDS},
                        "questions": [{"field": "ai", "reason": "REVIEW_UNAVAILABLE",
                                       "questionId": "confirm_ai"}], "error": "PROVIDER_TIMEOUT"}
        row = run_case(case, "test-key", provider=lambda *args: b"reply-secret",
                       analyzer_factory=FakeAnalyzer)
        self.assertEqual(calls, [(case["document"], "T01")])
        self.assertEqual(row["provider_calls"], 1)
        self.assertEqual(row["outcome"], "needs_confirmation")
        self.assertEqual(row["correct_suggestions"], 1)
        self.assertEqual(row["wrong_suggestions"], 0)
        self.assertEqual(row["questions"], 1)
        self.assertNotIn("secret-source", json.dumps(row))
        self.assertNotIn("test-key", json.dumps(row))
        self.assertNotIn("reply-secret", json.dumps(row))

    def test_fixed_failure_denominator_and_safety_gate(self):
        rows = [
            {"id": "A", "kind": "full", "outcome": "complete", "analysis_runs": 1, "provider_calls": 3,
             "elapsed_ms": 100, "correct_suggestions": 0, "wrong_suggestions": 1,
             "questions": 0, "structural_evidence_errors": 0,
             "false_confirmations": 1},
            {"id": "B", "kind": "focus", "outcome": "needs_confirmation", "analysis_runs": 1,
             "provider_calls": 6, "elapsed_ms": 61000, "correct_suggestions": 2,
             "wrong_suggestions": 0, "questions": 2,
             "structural_evidence_errors": 0, "false_confirmations": 0},
            {"id": "C", "kind": "full", "outcome": "failed", "analysis_runs": 1, "provider_calls": 1,
             "elapsed_ms": 200, "correct_suggestions": 0, "wrong_suggestions": 0,
             "questions": 0, "structural_evidence_errors": 0,
             "false_confirmations": 0},
        ]
        summary = aggregate(rows, planned=3)
        self.assertEqual(summary["planned_cases"], 3)
        self.assertEqual(summary["failed_cases"], 1)
        self.assertEqual(summary["prior_failure_cases"], 2)
        self.assertEqual(summary["correct_suggestions_from_prior_failures"], 2)
        self.assertEqual(summary["questions"], 2)
        self.assertEqual(summary["wrong_auto_confirmations"], 1)
        self.assertFalse(summary["gate"]["observed_60s_limit"])
        self.assertFalse(summary["gate"]["zero_wrong_auto_confirmations"])

    def test_written_artifact_has_no_source_or_response(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "results.json"
            write_json(path, [{"id": "T01", "outcome": "failed", "error": "PROVIDER_TIMEOUT"}])
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("document", text)
            self.assertNotIn("response", text)
            self.assertEqual(json.loads(text)[0]["error"], "PROVIDER_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
