"""Safe scoring for the candidate-first opt-in path."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai.real_document_holdout import PreparedCase


class CandidateFirstRealEvaluationTests(unittest.TestCase):
    def test_result_contains_counts_and_ids_but_no_source_or_profile_values(self):
        from agentfit_ai.candidate_first_real_evaluation import evaluate_cases

        case = PreparedCase("H01", "private-source-fragment", [
            {"id": "C01", "field": "project_name",
             "contains_any": ["Alpha"]}], "a", "b", None, 0, 0)
        def runner(text, document_id, key):
            self.assertEqual(text, case.text)
            return {"outcome": "candidate_profile",
                    "profile": {"data": {"project_name": "Alpha"}},
                    "candidateCount": 2, "rejectedCandidateCount": 0,
                    "rejectedReasons": {"ambiguous_anchor": 2,
                                        "private-response": 1},
                    "reviewIssueCount": 0, "unresolvedFields": []}
        result = evaluate_cases([case], "synthetic-key", runner=runner)
        self.assertEqual(result["complete"], 1)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["rows"][0]["rejected_reasons"],
                         {"ambiguous_anchor": 2})
        self.assertIsInstance(result["rows"][0]["elapsed_ms"], int)
        self.assertNotIn("Alpha", json.dumps(result))
        self.assertNotIn(case.text, json.dumps(result))

    def test_unreviewed_result_is_not_counted_as_complete(self):
        from agentfit_ai.candidate_first_real_evaluation import evaluate_cases

        case = PreparedCase("H01", "document", [
            {"id": "C01", "field": "project_name",
             "contains_any": ["Alpha"]}], "a", "b", None, 0, 0)
        def runner(text, document_id, key):
            return {"outcome": "needs_confirmation",
                    "profile": {"data": {"project_name": "Alpha"}},
                    "candidateCount": 1, "rejectedCandidateCount": 0,
                    "reviewIssueCount": 1,
                    "unresolvedFields": ["project_name"]}
        result = evaluate_cases([case], "synthetic-key", runner=runner)
        self.assertEqual(result["complete"], 0)
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["suggestion_matched"], 1)
        self.assertEqual(result["suggestion_checked"], 1)
        self.assertEqual(result["rows"][0]["outcome"], "needs_confirmation")

    def test_manifest_failure_never_loads_key(self):
        from agentfit_ai import candidate_first_real_evaluation as trial

        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            output = Path(temp) / "result.json"
            with (patch.object(sys, "argv", ["trial", "--live", "--manifest",
                         str(manifest), "--manifest-sha256", "bad",
                         "--output", str(output)]),
                  patch.object(trial, "load_key", side_effect=AssertionError(
                      "key loaded before privacy preflight"))):
                with self.assertRaises(SystemExit):
                    trial.main()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
