"""Synthetic PDF to grounded candidate end-to-end evaluation contracts."""

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agentfit_ai.docling_structured_trial import StructuredDocument
from agentfit_ai.document_extraction import DocumentExtractionError, ExtractedDocument

try:
    from agentfit_ai.docling_grounding_evaluation import (
        locate_gold, evaluate_cases, render_structured_pdf)
except ImportError:
    locate_gold = evaluate_cases = render_structured_pdf = None


def extracted(text):
    return StructuredDocument(
        ExtractedDocument("PDF", text, 20, len(text), 1,
                          [{"page": 1, "start": 0, "end": len(text)}]), 0, 0)


def candidate(quote, anchor):
    return SimpleNamespace(
        extraction_class="candidate", extraction_text=quote,
        attributes={"anchor": anchor}, char_interval=None,
        alignment_status=None)


class DoclingGroundingEvaluationTests(unittest.TestCase):
    def test_pinned_fixture_hash_is_stable_across_git_line_endings(self):
        from agentfit_ai import docling_grounding_evaluation as trial

        original = trial.STRUCTURED_CASES_PATH.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(len(trial.load_cases("structured")), 4)
        with patch.object(Path, "read_bytes", return_value=original.replace(
                b"\n", b"\r\n")):
            self.assertEqual(len(trial.load_cases("structured")), 4)

    def test_classifier_receives_mentions_without_gold_and_reorders_ids(self):
        from agentfit_ai.docling_grounding_evaluation import classify_candidate_mentions

        line = "CedarDB는 검토하고 BirchDB는 확정했다."
        items = [candidate("CedarDB", line), candidate("BirchDB", line)]

        def transport(payload, key, timeout):
            self.assertEqual(key, "synthetic-key")
            self.assertNotIn("expected_decision", json.dumps(payload))
            self.assertNotIn("expected_status", json.dumps(payload))
            response = {"model": "solar-pro4", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "labels": [
                        {"index": 1, "field": "database", "status": "confirmed"},
                        {"index": 0, "field": "database", "status": "tentative"}]})}}]}
            return json.dumps(response).encode()

        self.assertEqual(classify_candidate_mentions(
            line, items, "synthetic-key", transport=transport), [
                {"field": "database", "status": "tentative"},
                {"field": "database", "status": "confirmed"}])

    def test_classifier_defines_database_and_feature_independently(self):
        from agentfit_ai.docling_grounding_evaluation import classify_candidate_mentions

        def transport(payload, key, timeout):
            instruction = payload["messages"][0]["content"].lower()
            self.assertIn("storage engine", instruction)
            self.assertIn("product capabilities", instruction)
            self.assertIn("independently", instruction)
            response = {"model": "solar-pro4", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "labels": [{"index": 0, "field": "features",
                                "status": "confirmed"}]})}}]}
            return json.dumps(response).encode()

        result = classify_candidate_mentions(
            "검색을 제공한다.", [candidate("검색", "검색을 제공한다.")],
            "synthetic-key", transport=transport)
        self.assertEqual(result, [{"field": "features", "status": "confirmed"}])

    def test_structured_fixture_is_a_real_heading_and_table(self):
        import importlib.util
        if not (importlib.util.find_spec("docling") and
                importlib.util.find_spec("reportlab")):
            self.skipTest("optional experiment dependencies unavailable")
        from agentfit_ai.docling_structured_trial import convert_structured_pdf_bytes

        pdf = render_structured_pdf([
            "기능 결정", "기능|상태", "Search|확정", "Export|검토"])
        result = convert_structured_pdf_bytes(pdf)
        self.assertEqual((result.heading_count, result.table_count), (1, 1))
        self.assertIn("| Search", result.extracted.text)
        self.assertIn("| Export", result.extracted.text)

    def test_pinned_structured_cases_have_unique_page_gold(self):
        import importlib.util
        if not (importlib.util.find_spec("docling") and
                importlib.util.find_spec("reportlab")):
            self.skipTest("optional experiment dependencies unavailable")
        from agentfit_ai.docling_grounding_evaluation import load_cases
        from agentfit_ai.docling_structured_trial import convert_structured_pdf_bytes

        cases = load_cases("structured")
        result = convert_structured_pdf_bytes(render_structured_pdf(cases[0]["lines"]))
        self.assertEqual((result.heading_count, result.table_count), (1, 1))
        for case in cases:
            with self.subTest(case=case["id"]):
                start, end, page = locate_gold(
                    result.extracted, case["anchor"], case["quote"])
                self.assertEqual(page, 1)
                self.assertEqual(result.extracted.text[start:end], case["quote"])

    def test_gold_location_requires_unique_anchor_and_one_page(self):
        self.assertIsNotNone(locate_gold)
        source = extracted("검토 DB는 CedarDB다.\n운영 DB는 CedarDB로 확정했다.")
        start = source.extracted.text.rindex("CedarDB")
        self.assertEqual(locate_gold(source.extracted,
                                     "운영 DB는 CedarDB로 확정했다.", "CedarDB"),
                         (start, start + 7, 1))
        with self.assertRaises(ValueError):
            locate_gold(source.extracted, "CedarDB", "CedarDB")
        with self.assertRaises(ValueError):
            locate_gold(extracted("aaaa").extracted, "aaa", "aaa")

    def test_paired_cases_share_pdf_and_model_call_without_source_output(self):
        self.assertIsNotNone(evaluate_cases)
        text = "검토 DB는 CedarDB다.\n운영 DB는 CedarDB로 확정했다."
        lines = ["검토 DB는 CedarDB다.", "운영 DB는 CedarDB로 확정했다."]
        cases = [
            {"id": "R01", "category": "repeat", "lines": lines,
             "anchor": lines[0], "quote": "CedarDB", "field": "database",
             "state": "present", "expected_decision": "review"},
            {"id": "R02", "category": "repeat", "lines": lines,
             "anchor": lines[1], "quote": "CedarDB", "field": "database",
             "state": "present", "expected_decision": "allow"}]
        calls = {"pdf": 0, "model": 0}

        def converter(raw):
            calls["pdf"] += 1
            return extracted(text)

        def model(document, key):
            calls["model"] += 1
            return [candidate("CedarDB", lines[0]),
                    candidate("CedarDB", lines[1])]

        def classify(document, extracted, key):
            return [{"field": "database", "status": "tentative"},
                    {"field": "database", "status": "confirmed"}]

        report = evaluate_cases(cases, "synthetic-key", converter=converter,
                                extractor=model, classifier=classify,
                                renderer=lambda _: b"%PDF-synthetic")
        self.assertEqual(calls, {"pdf": 1, "model": 1})
        self.assertEqual((report["completed"], report["failed"]), (2, 0))
        self.assertEqual((report["false_auto_confirmations"],
                          report["missed_allows"]), (0, 0))
        saved = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("CedarDB", saved)
        self.assertNotIn("synthetic-key", saved)
        self.assertNotIn("검토 DB", saved)

    def test_wrong_model_field_cannot_be_hidden_by_gold_field(self):
        line = "운영 DB는 CedarDB로 확정했다."
        cases = [{"id": "R02", "category": "repeat", "lines": [line],
                  "anchor": line, "quote": "CedarDB", "field": "database",
                  "state": "present", "expected_decision": "allow"}]
        report = evaluate_cases(
            cases, "synthetic-key", converter=lambda raw: extracted(line),
            extractor=lambda document, key: [candidate("CedarDB", line)],
            classifier=lambda document, items, key: [
                {"field": "features", "status": "confirmed"}],
            renderer=lambda _: b"%PDF-synthetic")
        self.assertEqual(report["rows"][0]["decision"], "allow")
        self.assertEqual(report["rows"][0]["false_auto_confirmation"], 1)
        self.assertEqual(report["rows"][0]["missed_allow"], 1)
        self.assertEqual(report["rows"][0]["field_exact"], False)

    def test_classifier_failure_is_shared_and_never_auto_confirms(self):
        line = "운영 DB는 CedarDB로 확정했다."
        cases = [{"id": name, "category": "repeat", "lines": [line],
                  "anchor": line, "quote": "CedarDB", "field": "database",
                  "state": "present", "expected_decision": "allow"}
                 for name in ("R01", "R02")]
        calls = []

        def fail(document, items, key):
            calls.append(1)
            raise RuntimeError("secret model response")

        report = evaluate_cases(
            cases, "synthetic-key", converter=lambda raw: extracted(line),
            extractor=lambda document, key: [candidate("CedarDB", line)],
            classifier=fail, renderer=lambda _: b"%PDF-synthetic")
        self.assertEqual(len(calls), 1)
        self.assertEqual((report["completed"], report["failed"]), (0, 2))
        self.assertTrue(all(row["error"] == "CLASSIFICATION_FAILED"
                            for row in report["rows"]))
        self.assertNotIn("secret", json.dumps(report))

    def test_pdf_failure_is_shared_without_calling_model(self):
        cases = [{"id": "N01", "category": "negation",
                  "lines": ["실시간 검색은 제공하지 않는다."],
                  "anchor": "실시간 검색은 제공하지 않는다.",
                  "quote": "실시간 검색", "field": "features",
                  "state": "present", "expected_decision": "review"}]

        def failed_converter(raw):
            raise DocumentExtractionError("PDF_PARTIAL_TEXT")

        def unexpected_model(document, key):
            raise AssertionError("provider should not run")

        report = evaluate_cases(cases, "synthetic-key",
                                converter=failed_converter,
                                extractor=unexpected_model,
                                renderer=lambda _: b"%PDF-synthetic")
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["provider_calls"], 0)
        self.assertEqual(report["rows"][0]["error"], "PDF_PARTIAL_TEXT")

    def test_pdf_exception_text_is_never_in_safe_results(self):
        cases = [{"id": "N01", "category": "negation",
                  "lines": ["실시간 검색은 제공하지 않는다."],
                  "anchor": "실시간 검색은 제공하지 않는다.",
                  "quote": "실시간 검색", "field": "features",
                  "state": "present", "expected_decision": "review"}]

        def failed_converter(raw):
            raise DocumentExtractionError("Secret source content")

        report = evaluate_cases(cases, "synthetic-key",
                                converter=failed_converter,
                                extractor=lambda document, key: [],
                                renderer=lambda _: b"%PDF-synthetic")
        self.assertEqual(report["rows"][0]["error"], "PDF_WORKER_FAILED")
        self.assertNotIn("Secret", json.dumps(report))

    def test_cli_requires_live_and_pinned_cases_before_key_loading(self):
        from agentfit_ai import docling_grounding_evaluation as trial

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            with (patch.object(sys, "argv", ["trial", "--output", str(output)]),
                  patch.object(trial, "load_key", side_effect=AssertionError(
                      "key must not be loaded"))):
                with self.assertRaises(SystemExit):
                    trial.main()
            with (patch.object(sys, "argv", ["trial", "--live", "--output",
                                                   str(output)]),
                  patch.object(trial, "CASES_SHA256", "bad hash"),
                  patch.object(trial, "load_key", side_effect=AssertionError(
                      "key must not be loaded"))):
                with self.assertRaises(SystemExit):
                    trial.main()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
