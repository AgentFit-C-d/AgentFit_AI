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
    from agentfit_ai.docling_grounding_evaluation import locate_gold, evaluate_cases
except ImportError:
    locate_gold = evaluate_cases = None


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

        report = evaluate_cases(cases, "synthetic-key", converter=converter,
                                extractor=model, renderer=lambda _: b"%PDF-synthetic")
        self.assertEqual(calls, {"pdf": 1, "model": 1})
        self.assertEqual((report["completed"], report["failed"]), (2, 0))
        self.assertEqual((report["false_auto_confirmations"],
                          report["missed_allows"]), (0, 0))
        saved = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("CedarDB", saved)
        self.assertNotIn("synthetic-key", saved)
        self.assertNotIn("검토 DB", saved)

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
