"""Safe same-PDF comparison across the three extraction paths."""

import json
import unittest

from agentfit_ai.document_extraction import DocumentExtractionError, ExtractedDocument
from agentfit_ai.docling_structured_trial import StructuredDocument

try:
    from agentfit_ai.docling_pdf_comparison import compare_pdf_bytes
except ImportError:
    compare_pdf_bytes = None


def extracted(text):
    return ExtractedDocument("PDF", text, 20, len(text), 1,
                             [{"page": 1, "start": 0, "end": len(text)}])


class DoclingPdfComparisonTests(unittest.TestCase):
    def test_comparison_returns_only_counts_and_coverage(self):
        self.assertIsNotNone(compare_pdf_bytes)
        report = compare_pdf_bytes(
            b"%PDF-synthetic",
            pypdf_extractor=lambda raw: extracted("Secret Alpha Beta"),
            native_extractor=lambda raw: extracted("Secret Alpha Beta"),
            structured_extractor=lambda raw: StructuredDocument(
                extracted("Secret Alpha Beta Gamma"), 1, 1))
        self.assertEqual(report["standard"]["headings"], 1)
        self.assertEqual(report["standard"]["tables"], 1)
        self.assertEqual(report["comparison"]["pypdf_tokens_in_standard"], 1.0)
        self.assertNotIn("Secret", json.dumps(report))
        self.assertNotIn("Alpha", json.dumps(report))

    def test_each_extractor_failure_is_recorded_without_raw_exception(self):
        def native_failure(raw):
            raise RuntimeError("Secret content in exception")

        report = compare_pdf_bytes(
            b"%PDF-synthetic",
            pypdf_extractor=lambda raw: extracted("Alpha"),
            native_extractor=native_failure,
            structured_extractor=lambda raw: StructuredDocument(
                extracted("Alpha"), 0, 0))
        self.assertEqual(report["native"]["status"], "failed")
        self.assertEqual(report["native"]["error"], "EXTRACTION_FAILED")
        self.assertNotIn("Secret", json.dumps(report))

    def test_structured_failure_does_not_become_native_success(self):
        def standard_failure(raw):
            raise DocumentExtractionError("PDF_PARTIAL_TEXT")

        report = compare_pdf_bytes(
            b"%PDF-synthetic",
            pypdf_extractor=lambda raw: extracted("Alpha"),
            native_extractor=lambda raw: extracted("Alpha"),
            structured_extractor=standard_failure)
        self.assertEqual(report["standard"],
                         {"status": "failed", "error": "PDF_PARTIAL_TEXT"})
        self.assertEqual(report["comparison"], {"status": "not_evaluated"})


if __name__ == "__main__":
    unittest.main()
