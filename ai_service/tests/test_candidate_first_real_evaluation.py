"""Safe scoring for the candidate-first opt-in path."""

import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai.real_document_holdout import PreparedCase


class CandidateFirstRealEvaluationTests(unittest.TestCase):
    def test_review_diagnostics_survive_provider_failure(self):
        from agentfit_ai.candidate_first_real_evaluation import evaluate_cases
        from agentfit_ai.candidate_first_profile import CandidatePipelineError
        case = PreparedCase('H02', 'private-source', [
            {'id': 'C01', 'field': 'project_name', 'contains_any': ['Alpha']}], 'a', 'b', None, 0, 0)
        def runner(text, document_id, key, *, review_calls):
            review_calls.append({'stage': 'candidate_batch', 'batch_index': 1, 'validated': False})
            raise CandidatePipelineError('COVERAGE_REVIEW_FAILED', 'INCOMPLETE_RESPONSE')
        result = evaluate_cases([case], 'fake', runner=runner, review_diagnostics=True)
        self.assertEqual(result['rows'][0]['review_calls'][0]['stage'], 'candidate_batch')
        self.assertEqual(result['rows'][0]['outcome'], 'failed')

    def test_cli_selects_split_review_and_records_mode(self):
        from agentfit_ai import candidate_first_real_evaluation as trial

        case = PreparedCase('H02', 'private-source-fragment', [
            {'id': 'C01', 'field': 'project_name', 'contains_any': ['Alpha']}],
            'a', 'b', None, 0, 0)
        def runner(text, document_id, key, *, split_review, review_calls, adaptive_review):
            self.assertTrue(split_review)
            self.assertTrue(adaptive_review)
            review_calls.append({'stage': 'source_coverage', 'validated': True})
            return {'outcome': 'needs_confirmation', 'profile': {'data': {'project_name': 'Alpha'}},
                    'candidateCount': 1, 'rejectedCandidateCount': 0,
                    'reviewIssueCount': 1, 'unresolvedFields': ['features']}
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / 'manifest.json'
            raw = b'{"cases": []}'
            manifest.write_bytes(raw)
            output = Path(temp) / 'result.json'
            with (patch.object(sys, 'argv', ['trial', '--live', '--manifest', str(manifest),
                    '--manifest-sha256', hashlib.sha256(raw).hexdigest(),
                    '--output', str(output), '--split-review', '--review-diagnostics', '--adaptive-review']),
                  patch.object(trial, 'prepare_cases', return_value=[case]),
                  patch.object(trial, 'load_key', return_value='fake-key'),
                  patch.object(trial, 'analyze_candidate_first', side_effect=runner)):
                self.assertEqual(trial.main(), 0)
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['review_mode'], 'split')
            self.assertTrue(result['adaptive_review'])
            self.assertEqual(result['complete'], 0)
            self.assertEqual(result['rows'][0]['review_calls'][0]['stage'], 'source_coverage')

    def test_stage_diagnostics_survive_a_later_provider_failure(self):
        from agentfit_ai.candidate_first_real_evaluation import evaluate_cases
        from agentfit_ai.candidate_first_profile import CandidatePipelineError

        case = PreparedCase('H02', 'Alpha', [
            {'id': 'C01', 'field': 'project_name', 'contains_any': ['Alpha']}],
            'a', 'b', None, 0, 0)
        def runner(text, document_id, key, *, observer):
            observer('grounded', {'candidates': [{'id': 'C000', 'start': 0, 'end': 5}], 'rejected': []})
            raise CandidatePipelineError('CLASSIFICATION_FAILED')
        result = evaluate_cases([case], 'fake-key', runner=runner, stage_diagnostics=True)
        row = result['rows'][0]
        self.assertEqual(row['outcome'], 'failed')
        self.assertTrue(row['stage_checks'][0]['grounded'])
        self.assertIsNone(row['stage_checks'][0]['classified'])
        self.assertEqual(row['stage_checks'][0]['first_unmatched_stage'], 'unobserved')
        self.assertNotIn('Alpha', json.dumps(result))

    def test_cli_selects_source_occurrences_and_preserves_safe_rejection_reason(self):
        from agentfit_ai import candidate_first_real_evaluation as trial

        case = PreparedCase('H02', 'private-source-fragment', [
            {'id': 'C01', 'field': 'project_name', 'contains_any': ['Alpha']}],
            'a', 'b', None, 0, 0)
        def runner(text, document_id, key, *, source_occurrences):
            self.assertTrue(source_occurrences)
            return {'outcome': 'needs_confirmation', 'profile': {'data': {'project_name': 'Alpha'}},
                    'candidateCount': 1, 'rejectedCandidateCount': 1,
                    'rejectedReasons': {'source_quote_absent': 1},
                    'reviewIssueCount': 0, 'unresolvedFields': []}
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / 'manifest.json'
            raw = b'{"cases": []}'
            manifest.write_bytes(raw)
            output = Path(temp) / 'result.json'
            with (patch.object(sys, 'argv', ['trial', '--live', '--manifest', str(manifest),
                    '--manifest-sha256', hashlib.sha256(raw).hexdigest(),
                    '--output', str(output), '--source-occurrences']),
                  patch.object(trial, 'prepare_cases', return_value=[case]),
                  patch.object(trial, 'load_key', return_value='fake-key'),
                  patch.object(trial, 'analyze_candidate_first', side_effect=runner)):
                self.assertEqual(trial.main(), 0)
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['grounding_mode'], 'source-occurrences')
            self.assertEqual(result['rows'][0]['rejected_reasons'], {'source_quote_absent': 1})
            self.assertNotIn(case.text, output.read_text(encoding='utf-8'))

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
        self.assertEqual(result["rows"][0]["suggestion_failed_check_ids"], [])
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
