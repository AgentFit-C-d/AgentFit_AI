import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentfit_ai.public_holdout import MANIFEST, load_manifest, score_profile, verify_document
from agentfit_ai.public_holdout_evaluation import SafeTraceSolarAnalyzer, evaluate_case, main, summarize
from agentfit_ai.profile import FIELDS


class PublicHoldoutTests(unittest.TestCase):
    def test_line_evidence_flag_selects_opt_in_analyzer_and_records_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result"

            class FakeLineAnalyzer:
                def __init__(self, *args, **kwargs):
                    self.safe_calls = []

                def analyze_recoverable(self, document, document_id):
                    return {"outcome": "failed", "error": "INVALID_EVIDENCE"}

            with patch.object(sys, "argv", ["evaluate", "--live", "--output",
                                                str(output), "--line-evidence"]), \
                 patch("agentfit_ai.public_holdout_evaluation.load_manifest",
                       return_value=[self.case]), \
                 patch("agentfit_ai.public_holdout_evaluation.fetch_document",
                       return_value=self.document), \
                 patch("agentfit_ai.public_holdout_evaluation.load_key",
                       return_value="synthetic-key"), \
                 patch("agentfit_ai.public_holdout_evaluation.SafeTraceLineEvidenceAnalyzer",
                       FakeLineAnalyzer), \
                 patch("agentfit_ai.public_holdout_evaluation.SafeTraceSolarAnalyzer",
                       side_effect=AssertionError("base analyzer selected")):
                self.assertEqual(main(), 0)
            plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
            self.assertTrue(plan["line_evidence"])

    def test_evaluation_accepts_repair_context_options_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(sys, "argv", ["evaluate", "--live", "--output",
                                            str(Path(temp) / "run"),
                                            "--repair-context-options"]), \
                 patch("agentfit_ai.public_holdout_evaluation.load_manifest",
                       side_effect=RuntimeError("parsed")):
                with self.assertRaisesRegex(RuntimeError, "parsed"):
                    main()

    def test_evaluation_accepts_parallel_first_pass_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(sys, "argv", ["evaluate", "--live", "--output",
                                            str(Path(temp) / "run"),
                                            "--parallel-first-pass"]), \
                 patch("agentfit_ai.public_holdout_evaluation.load_manifest",
                       side_effect=RuntimeError("parsed")):
                with self.assertRaisesRegex(RuntimeError, "parsed"):
                    main()

    def test_frozen_manifest_has_three_distinct_sources(self):
        cases = load_manifest()
        self.assertEqual([case["id"] for case in cases],
                         ["actual-product", "mealie-readme", "immich-readme"])

    def test_consumed_korean_corpus_is_tuning_not_fresh_holdout(self):
        path = MANIFEST.parent.parent / "korean-public-holdout/manifest.json"
        cases = load_manifest(path)
        self.assertEqual(len(cases), 5)
        self.assertEqual(len({case["repo"] for case in cases}), 5)

    def test_manifest_partition_must_match_explicit_evaluation_purpose(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            source = json.loads(MANIFEST.read_text(encoding="utf-8"))
            source["partition"] = "heldout"
            path.write_text(json.dumps(source), encoding="utf-8")
            self.assertEqual(len(load_manifest(path, expected_partition="heldout")), 3)
            with self.assertRaises(ValueError):
                load_manifest(path)
            with self.assertRaises(ValueError):
                load_manifest(path, expected_partition="unknown")

    def test_cli_rejects_wrong_partition_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            output = Path(temp) / "result"
            source = json.loads(MANIFEST.read_text(encoding="utf-8"))
            source["partition"] = "heldout"
            manifest.write_text(json.dumps(source), encoding="utf-8")
            with patch("sys.argv", ["eval", "--live", "--output", str(output),
                                    "--manifest", str(manifest), "--partition", "tuning"]):
                with self.assertRaisesRegex(ValueError, "invalid public manifest"):
                    main()
            self.assertFalse(output.exists())

    def setUp(self):
        self.document = "# Acme\nVue powers the frontend.\nUsers can import recipes.\n"
        self.case = {
            "id": "public-acme",
            "repo": "example/acme",
            "commit": "a" * 40,
            "path": "README.md",
            "sha256": hashlib.sha256(self.document.encode()).hexdigest(),
            "checks": {
                "project_name": [{"aliases": ["Acme"], "quote": "# Acme"}],
                "frontend": [{"aliases": ["Vue"], "quote": "Vue powers the frontend"}],
                "features": [{"aliases": ["import recipes", "recipe imports"],
                              "quote": "Users can import recipes"}],
            },
        }

    def test_document_hash_and_quotes_must_match_before_scoring(self):
        self.assertEqual(verify_document(self.case, self.document.encode()), self.document)
        with self.assertRaises(ValueError):
            verify_document(self.case, self.document.replace("Vue", "React").encode())
        bad = {**self.case, "checks": {"frontend": [
            {"aliases": ["Vue"], "quote": "React powers the frontend"}]}}
        with self.assertRaises(ValueError):
            verify_document(bad, self.document.encode())

    def test_unsupported_url_and_oversized_document_are_rejected(self):
        bad = {**self.case, "repo": "../private"}
        with self.assertRaises(ValueError):
            verify_document(bad, self.document.encode())
        with self.assertRaises(ValueError):
            verify_document(self.case, b"x" * 100001)

    def test_explicit_unknown_fields_are_validated_and_must_not_overlap_gold(self):
        case = {**self.case, "unknown_fields": ["ai", "database"]}
        self.assertEqual(verify_document(case, self.document.encode()), self.document)
        for fields in (["ai", "ai"], ["ai", "not_a_field"], ["frontend"]):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                verify_document({**self.case, "unknown_fields": fields},
                                self.document.encode())

    def test_explicit_unknown_fields_count_null_and_non_null_separately(self):
        case = {**self.case, "unknown_fields": ["ai", "database"]}
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        score = score_profile(case, self.document, {"data": data, "evidence": evidence})
        self.assertEqual(score["expected_unknown_fields"], 2)
        self.assertEqual(score["unknown_fields_preserved"], 2)
        self.assertEqual(score["unknown_fields_non_null"], 0)
        data["ai"] = ["unsupported model"]
        score = score_profile(case, self.document, {"data": data, "evidence": evidence})
        self.assertEqual(score["unknown_fields_preserved"], 1)
        self.assertEqual(score["unknown_fields_non_null"], 1)
        self.assertEqual(score["unassessed_values"], 0)

    def test_partial_score_separates_value_evidence_and_unassessed_fields(self):
        document = verify_document(self.case, self.document.encode())
        data = {field: None for field in (
            "project_name", "project_type", "domain", "frontend", "backend",
            "ai", "database", "deployment", "features", "external_integrations")}
        data.update(project_name="Acme", frontend=["Vue"],
                    features=["import recipes", "shopping list"])
        evidence = {field: [] for field in data}
        evidence["project_name"] = [self.span(document, "# Acme")]
        evidence["frontend"] = [self.span(document, "Vue powers the frontend")]
        evidence["features"] = [self.span(document, "Users can import recipes")]
        result = score_profile(self.case, document, {"data": data, "evidence": evidence})
        self.assertEqual(result["matched_checks"], 3)
        self.assertEqual(result["wrong_evidence_checks"], 0)
        self.assertEqual(result["unassessed_values"], 1)

    def test_wrong_evidence_is_distinct_from_missing_alias(self):
        document = verify_document(self.case, self.document.encode())
        data = {field: None for field in (
            "project_name", "project_type", "domain", "frontend", "backend",
            "ai", "database", "deployment", "features", "external_integrations")}
        data.update(project_name="Acme", frontend=["Vue"], features=["import recipes"])
        evidence = {field: [] for field in data}
        evidence["project_name"] = [self.span(document, "# Acme")]
        evidence["frontend"] = [self.span(document, "# Acme")]
        evidence["features"] = [self.span(document, "Users can import recipes")]
        result = score_profile(self.case, document, {"data": data, "evidence": evidence})
        self.assertEqual(result["matched_checks"], 2)
        self.assertEqual(result["wrong_evidence_checks"], 1)
        self.assertEqual(result["missing_alias_checks"], 0)

    def test_evidence_may_cite_exact_value_without_list_marker(self):
        document = "- 웹 푸시 알림\n"
        case = {"checks": {"features": [{"aliases": ["웹 푸시 알림"],
                                          "quote": "- 웹 푸시 알림"}]}}
        profile = self.profile_with("features", ["웹 푸시 알림"],
                                    [{"start": 2, "end": len(document) - 1}])
        score = score_profile(case, document, profile)
        self.assertEqual(score["matched_checks"], 1)
        self.assertEqual(score["wrong_evidence_checks"], 0)

    def test_same_value_cited_at_other_location_is_indeterminate(self):
        document = "- 웹 푸시 알림\n계획: 웹 푸시 알림\n"
        case = {"checks": {"features": [{"aliases": ["웹 푸시 알림"],
                                          "quote": "- 웹 푸시 알림"}]}}
        start = document.index("웹 푸시 알림", document.index("계획:"))
        profile = self.profile_with("features", ["웹 푸시 알림"],
                                    [{"start": start, "end": start + len("웹 푸시 알림")}])
        score = score_profile(case, document, profile)
        self.assertEqual(score["wrong_evidence_checks"], 0)
        self.assertEqual(score["indeterminate_evidence_checks"], 1)
        self.assertEqual(score["matched_checks"], 0)

    def test_gold_location_wins_when_alternate_location_is_also_cited(self):
        document = "- 웹 푸시 알림\n계획: 웹 푸시 알림\n"
        case = {"checks": {"features": [{"aliases": ["웹 푸시 알림"],
                                          "quote": "- 웹 푸시 알림"}]}}
        start = document.index("웹 푸시 알림", document.index("계획:"))
        profile = self.profile_with("features", ["웹 푸시 알림"], [
            {"start": start, "end": start + len("웹 푸시 알림")},
            {"start": 2, "end": 2 + len("웹 푸시 알림")},
        ])
        score = score_profile(case, document, profile)
        self.assertEqual(score["matched_checks"], 1)
        self.assertEqual(score["wrong_evidence_checks"], 0)

    def test_shared_array_span_has_indeterminate_item_evidence(self):
        document = "Users can import recipes and create shopping lists."
        case = {"checks": {"features": [
            {"aliases": ["import recipes"], "quote": "import recipes"},
            {"aliases": ["create shopping lists"], "quote": "create shopping lists"}]}}
        profile = self.profile_with("features", ["import recipes", "create shopping lists"],
                                    [{"start": 0, "end": len(document)}])
        score = score_profile(case, document, profile)
        self.assertEqual(score["matched_checks"], 0)
        self.assertEqual(score["indeterminate_evidence_checks"], 2)
        self.assertEqual(sum(score[name] for name in (
            "matched_checks", "wrong_evidence_checks", "missing_alias_checks",
            "indeterminate_evidence_checks")), score["total_checks"])

    def test_one_value_matching_two_gold_checks_is_indeterminate(self):
        document = "Users can import recipes and export recipes."
        case = {"checks": {"features": [
            {"aliases": ["recipes"], "quote": "import recipes"},
            {"aliases": ["recipes"], "quote": "export recipes"}]}}
        start = document.index("import recipes")
        profile = self.profile_with("features", ["import recipes"],
                                    [{"start": start, "end": start + len("import recipes")}])
        score = score_profile(case, document, profile)
        self.assertEqual(score["matched_checks"], 0)
        self.assertEqual(score["indeterminate_evidence_checks"], 2)

    def test_alias_match_outside_gold_anchor_is_indeterminate(self):
        document = "Users can import recipes through a URL. Recipe import is listed elsewhere."
        case = {"checks": {"features": [{"aliases": ["Recipe import"],
                                          "quote": "import recipes through a URL"}]}}
        start = document.index("Recipe import")
        profile = self.profile_with("features", ["Recipe import"],
                                    [{"start": start, "end": start + len("Recipe import")}])
        score = score_profile(case, document, profile)
        self.assertEqual(score["indeterminate_evidence_checks"], 1)
        self.assertEqual(score["wrong_evidence_checks"], 0)

    def test_evaluation_retains_counts_without_profile_or_source(self):
        document = verify_document(self.case, self.document.encode())
        data = {field: None for field in (
            "project_name", "project_type", "domain", "frontend", "backend",
            "ai", "database", "deployment", "features", "external_integrations")}
        data["project_name"] = "Acme"
        evidence = {field: [] for field in data}
        evidence["project_name"] = [self.span(document, "# Acme")]

        class FakeAnalyzer:
            def analyze_recoverable(self, text, case_id):
                assert text == document and case_id == "public-acme"
                return {"outcome": "needs_confirmation", "error": "PROVIDER_TIMEOUT",
                        "profile": {"data": data, "evidence": evidence},
                        "fieldStates": {}, "questions": []}

        row = evaluate_case(self.case, document, FakeAnalyzer())
        self.assertEqual(row["matched_checks"], 1)
        self.assertEqual(row["missing_alias_checks"], 2)
        self.assertNotIn("profile", row)
        self.assertNotIn("document", row)
        summary = summarize([row], planned=3)
        self.assertEqual(summary["needs_confirmation_cases"], 1)
        self.assertEqual(summary["indeterminate_evidence_checks"], 0)
        self.assertEqual(summary["score_version"], "public-evidence-v4")
        self.assertFalse(summary["release_gate_passed"])

    def test_evaluation_summarizes_explicit_unknown_fields_without_raw_values(self):
        case = {**self.case, "unknown_fields": ["ai"]}
        document = verify_document(case, self.document.encode())
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}

        class FakeAnalyzer:
            def analyze_recoverable(self, text, case_id):
                return {"outcome": "needs_confirmation", "error": None,
                        "profile": {"data": data, "evidence": evidence},
                        "fieldStates": {}, "questions": []}

        row = evaluate_case(case, document, FakeAnalyzer())
        self.assertEqual(row["expected_unknown_fields"], 1)
        self.assertEqual(row["unknown_fields_preserved"], 1)
        self.assertEqual(row["unknown_fields_non_null"], 0)
        summary = summarize([row], planned=1)
        self.assertEqual(summary["expected_unknown_fields"], 1)
        self.assertEqual(summary["unknown_fields_preserved"], 1)
        self.assertNotIn("profile", summary)

    def test_safe_trace_keeps_final_failure_reason_without_raw_detail(self):
        analyzer = SafeTraceSolarAnalyzer("synthetic-key", evidence_contract=True)
        diagnostic = {"calls": [{"call": 3, "stage": "repair",
                                "outcome": "validation_failed", "error": "INVALID_EVIDENCE",
                                "validation_error": {"field": "features",
                                                     "reason": "QUOTE_NOT_FOUND",
                                                     "itemIndex": 0, "matchCount": 0,
                                                     "private": "secret source"}}]}
        analyzer._save_diagnostic(diagnostic, {3: b"private model reply"})
        self.assertEqual(analyzer.safe_calls,
                         [{"call": 3, "stage": "repair", "outcome": "validation_failed",
                           "error": "INVALID_EVIDENCE",
                           "validation": [{"field": "features", "reason": "QUOTE_NOT_FOUND",
                                           "itemIndex": 0, "matchCount": 0}]}])

    def test_safe_trace_retains_only_numeric_stage_timing(self):
        analyzer = SafeTraceSolarAnalyzer("synthetic-key", evidence_contract=True)
        analyzer._save_diagnostic({"calls": [{
            "call": 1, "stage": "core", "outcome": "validated",
            "request_bytes": 1234, "provider_elapsed_ms": 56,
            "elapsed_ms": 57, "private": "secret source"}]}, {})
        self.assertEqual(analyzer.safe_calls[0]["timing"],
                         {"request_bytes": 1234, "provider_elapsed_ms": 56,
                          "elapsed_ms": 57})
        self.assertNotIn("secret source", json.dumps(analyzer.safe_calls))

    def test_safe_trace_counts_offered_options_without_retaining_source(self):
        analyzer = SafeTraceSolarAnalyzer("synthetic-key", evidence_contract=True,
                                          repair_context_options=True)
        correction = analyzer._repair_correction(
            "이번 Atlas는 앱이다.\n비교 Atlas는 게임이다.",
            [{"field": "project_name", "code": "INVALID_EVIDENCE",
              "detail": {"reason": "AMBIGUOUS_QUOTE", "itemIndex": 0}}],
            {"project_name": {"state": "confirmed", "items": [
                {"value": "Atlas", "quote": "Atlas", "context": None,
                 "role": "product_fact"}]}})
        self.assertEqual(len(correction["evidenceOptions"]["project_name"]["options"]), 2)
        self.assertEqual(analyzer.safe_repair_option_counts,
                         {"fields": 1, "choices": 2})
        self.assertNotIn("Atlas", json.dumps(analyzer.safe_repair_option_counts))

    @staticmethod
    def span(document, quote):
        start = document.index(quote)
        return {"documentId": "public-acme", "start": start, "end": start + len(quote)}

    @staticmethod
    def profile_with(field, value, spans):
        data = dict.fromkeys(FIELDS)
        evidence = {name: [] for name in FIELDS}
        data[field] = value
        evidence[field] = spans
        return {"data": data, "evidence": evidence}


if __name__ == "__main__":
    unittest.main()
