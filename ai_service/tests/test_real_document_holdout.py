"""Private-document preflight and source-free quality scoring."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class RealDocumentHoldoutTests(unittest.TestCase):
    def test_redaction_removes_markdown_team_section(self):
        from agentfit_ai.real_document_holdout import redact_text

        source = "# Plan\n## 5. 팀 구성원 역할분배\n| 성명 |\n| 홍길동 |\n## 6. 기능\n검색 제공"
        result = redact_text("MARKDOWN", source)
        self.assertNotIn("홍길동", result)
        self.assertIn("검색 제공", result)

    def test_pdf_private_header_and_contact_data_never_leave_preflight(self):
        from agentfit_ai.real_document_holdout import redact_text

        source = "팀장 이름/학번/연락처 홍길동 12345678 01012345678\n프로젝트 메인 주제\n알림"
        self.assertEqual(redact_text("PDF", source), "프로젝트 메인 주제\n알림")
        with self.assertRaises(ValueError):
            redact_text("PDF", "팀장 01012345678\n경계가 없음")
        with self.assertRaises(ValueError):
            redact_text("PDF", "프로젝트 메인 주제\n01012345678")

    def test_private_manifest_requires_exact_approved_file_hash(self):
        from agentfit_ai.real_document_holdout import prepare_cases

        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "plan.md"
            source.write_text("## 5. 팀 구성원 역할분배\n홍길동\n## 6. 기능\n검색 제공",
                              encoding="utf-8")
            case = {"id": "H01", "kind": "MARKDOWN", "path": str(source),
                    "sha256": "wrong", "checks": [{"id": "C01", "field": "features",
                                                     "contains_any": ["검색"]}]}
            with self.assertRaises(ValueError):
                prepare_cases([case], allowed_hashes={"H01": "wrong"})
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            case["sha256"] = digest
            prepared = prepare_cases([case], allowed_hashes={"H01": digest})
            self.assertEqual(len(prepared), 1)
            self.assertNotIn("홍길동", prepared[0].text)

    def test_profile_checks_return_only_ids_and_counts(self):
        from agentfit_ai.real_document_holdout import score_profile

        checks = [{"id": "C01", "field": "project_name",
                   "contains_any": ["MyPort"]},
                  {"id": "C02", "field": "database", "expect_null": True}]
        profile = {"data": {"project_name": "MyPort", "database": None}}
        scored = score_profile(profile, checks)
        self.assertEqual(scored["matched"], 2)
        self.assertEqual(scored["total"], 2)
        self.assertNotIn("MyPort", json.dumps(scored))

    def test_cli_rejects_manifest_hash_before_loading_key(self):
        from agentfit_ai import real_document_holdout as trial

        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            output = Path(temp) / "result.json"
            with (patch.object(sys, "argv", ["trial", "--live", "--manifest",
                         str(manifest), "--manifest-sha256", "bad",
                         "--output", str(output)]),
                  patch.object(trial, "load_key", side_effect=AssertionError(
                      "key loaded before preflight"))):
                with self.assertRaises(SystemExit):
                    trial.main()
            self.assertFalse(output.exists())

    def test_diagnostic_timeout_is_explicit_and_opt_in(self):
        from agentfit_ai.real_document_holdout import make_analyzer

        with patch("agentfit_ai.real_document_holdout.SolarAnalyzer") as analyzer:
            make_analyzer("test-key", 40)
            self.assertEqual(analyzer.call_args.kwargs["analysis_timeout_seconds"], 40)
            self.assertFalse(analyzer.call_args.kwargs["experimental_long_timeout"])
            make_analyzer("test-key", 120)
            self.assertEqual(analyzer.call_args.kwargs["analysis_timeout_seconds"], 120)
            self.assertFalse(analyzer.call_args.kwargs["experimental_long_timeout"])
            make_analyzer("test-key", 600)
            self.assertTrue(analyzer.call_args.kwargs["experimental_long_timeout"])
            self.assertEqual(analyzer.call_args.kwargs["field_call_timeout_seconds"], 120)
        with self.assertRaises(ValueError):
            make_analyzer("test-key", 121)

    def test_failure_trace_exposes_only_stage_and_safe_error_code(self):
        from agentfit_ai.real_document_holdout import safe_trace

        diagnostic = {"elapsed_ms": 121000, "calls": [
            {"stage": "core", "outcome": "validation_failed",
             "error": "INVALID_EVIDENCE", "validation_errors": [
                 {"field": "database", "detail": "private quote"}]},
            {"stage": "repair", "outcome": "failed",
             "error": "PROVIDER_TIMEOUT", "raw": "private source"}]}
        self.assertEqual(safe_trace(diagnostic), {
            "elapsed_ms": 121000,
            "calls": [{"stage": "core", "outcome": "validation_failed",
                       "error": "INVALID_EVIDENCE"},
                      {"stage": "repair", "outcome": "failed",
                       "error": "PROVIDER_TIMEOUT"}]})

    def test_case_selection_happens_after_full_preflight(self):
        from agentfit_ai.real_document_holdout import PreparedCase, select_cases

        cases = [PreparedCase(case_id, "text", [], "a", "b", None, 0, 0)
                 for case_id in ("H01", "H02", "H03")]
        self.assertEqual(select_cases(cases, "H02"), [cases[1]])
        self.assertEqual(select_cases(cases, None), cases)
        with self.assertRaises(ValueError):
            select_cases(cases, "H04")

    def test_failed_evaluation_omits_private_diagnostic_detail(self):
        from agentfit_ai.real_document_holdout import PreparedCase, evaluate_cases
        from agentfit_ai.solar import AnalysisError

        private = "private-source-fragment"
        error = AnalysisError("INVALID_EVIDENCE")
        error.field = "features"
        error.detail = {"reason": "QUOTE_NOT_FOUND", "itemIndex": 1,
                        "quote": private}
        error.diagnostics = {"elapsed_ms": 42, "calls": [{
            "stage": "repair", "outcome": "validation_failed",
            "validation_error": {"detail": private}}]}

        class FailingAnalyzer:
            def analyze(self, document, document_id):
                raise error

        case = PreparedCase("H01", private, [], "a", "b", None, 0, 0)
        result = evaluate_cases([case], "test-key",
                                analyzer_factory=lambda _: FailingAnalyzer())
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["rows"][0]["evidence_failure"], {
            "field": "features", "reason": "QUOTE_NOT_FOUND", "itemIndex": 1})
        self.assertNotIn(private, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
