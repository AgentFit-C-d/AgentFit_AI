"""Input boundary tests for document extraction before any provider call."""

from io import BytesIO
import json
import unittest
from unittest.mock import patch
from subprocess import CompletedProcess

from pypdf import PdfReader, PdfWriter

try:
    from agentfit_ai.document_extraction import DocumentExtractionError, extract_document
except ImportError:
    DocumentExtractionError = extract_document = None


def sample_pdf(pages: list[str]) -> bytes:
    """Build a small real PDF without an external fixture or document data."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        page_number = len(objects) + 1
        stream_number = page_number + 1
        kids.append(f"{page_number} 0 R")
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
                        f"/Resources << /Font << /F1 3 0 R >> >> "
                        f"/Contents {stream_number} 0 R >>").encode("ascii"))
        content = (f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("ascii")
                   if text else b"")
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode("ascii") +
                       content + b"\nendstream")
    objects[1] = (f"<< /Type /Pages /Kids [{' '.join(kids)}] "
                  f"/Count {len(pages)} >>").encode("ascii")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                   f"startxref\n{xref}\n%%EOF\n").encode("ascii"))
    return bytes(output)


class DocumentExtractionTests(unittest.TestCase):
    def test_direct_text_counts_unicode_code_points_and_keeps_whitespace(self):
        self.assertIsNotNone(extract_document)
        result = extract_document("TEXT", "가😀\n")
        self.assertEqual(result.text, "가😀\n")
        self.assertEqual(result.character_count, 3)
        self.assertEqual(result.byte_size, 8)
        self.assertIsNone(result.page_count)
        self.assertEqual(result.page_spans, [])

    def test_direct_text_inclusive_limit_and_excess(self):
        self.assertIsNotNone(extract_document)
        self.assertEqual(extract_document("TEXT", "😀" * 100000).character_count, 100000)
        with self.assertRaises(DocumentExtractionError) as caught:
            extract_document("TEXT", "😀" * 100001)
        self.assertEqual(caught.exception.code, "DOCUMENT_TEXT_TOO_LONG")

    def test_direct_text_rejects_excess_length_before_utf8_encoding(self):
        with self.assertRaises(DocumentExtractionError) as caught:
            extract_document("TEXT", "x" * 100001 + "\ud800")
        self.assertEqual(caught.exception.code, "DOCUMENT_TEXT_TOO_LONG")

    def test_markdown_strict_utf8_and_leading_bom(self):
        self.assertIsNotNone(extract_document)
        result = extract_document("MARKDOWN", b"\xef\xbb\xbf# Alpha\n")
        self.assertEqual(result.text, "# Alpha\n")
        self.assertEqual(result.byte_size, 11)
        self.assertEqual(result.character_count, 8)
        with self.assertRaises(DocumentExtractionError) as caught:
            extract_document("MARKDOWN", b"\xff Secret")
        self.assertEqual(caught.exception.code, "DOCUMENT_INVALID_UTF8")
        self.assertNotIn("Secret", str(caught.exception))

    def test_markdown_file_limit_precedes_text_limit(self):
        self.assertIsNotNone(extract_document)
        with self.assertRaises(DocumentExtractionError) as caught:
            extract_document("MARKDOWN", b"x" * 10485761)
        self.assertEqual(caught.exception.code, "DOCUMENT_TOO_LARGE")

    def test_invalid_kind_content_and_empty_input(self):
        self.assertIsNotNone(extract_document)
        cases = [("HTML", "x", "INVALID_DOCUMENT_KIND"),
                 ("PDF", "x", "INVALID_DOCUMENT_CONTENT"),
                 ("MARKDOWN", "x", "INVALID_DOCUMENT_CONTENT"),
                 ("TEXT", b"x", "INVALID_DOCUMENT_CONTENT"),
                 ("TEXT", " \n ", "DOCUMENT_EMPTY"),
                 ("MARKDOWN", b"\n\t", "DOCUMENT_EMPTY")]
        for kind, content, code in cases:
            with self.subTest(kind=kind, code=code):
                with self.assertRaises(DocumentExtractionError) as caught:
                    extract_document(kind, content)
                self.assertEqual(caught.exception.code, code)

    def test_pdf_extracts_two_pages_and_keeps_page_offsets(self):
        payload = sample_pdf(["Alpha", "Beta"])
        self.assertEqual(len(PdfReader(BytesIO(payload)).pages), 2)
        try:
            result = extract_document("PDF", payload)
        except NotImplementedError:
            self.fail("PDF extraction is not implemented")
        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.byte_size, len(payload))
        self.assertEqual(len(result.page_spans), 2)
        first, second = result.page_spans
        self.assertEqual((first["page"], second["page"]), (1, 2))
        self.assertIn("Alpha", result.text[first["start"]:first["end"]])
        self.assertIn("Beta", result.text[second["start"]:second["end"]])
        self.assertEqual(result.text[first["end"]:second["start"]], "\n")

    def test_pdf_rejects_locked_and_corrupt_files_without_source(self):
        writer = PdfWriter(BytesIO(sample_pdf(["Secret"])))
        writer.encrypt("password")
        locked = BytesIO()
        writer.write(locked)
        for payload, code in ((locked.getvalue(), "PDF_LOCKED"),
                              (b"%PDF-1.4\nSecret broken", "PDF_INVALID"),
                              (b"not a pdf Secret", "PDF_INVALID")):
            with self.subTest(code=code):
                with self.assertRaises(DocumentExtractionError) as caught:
                    extract_document("PDF", payload)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn("Secret", str(caught.exception))

    def test_pdf_rejects_blank_and_partial_pages(self):
        for pages, code in (([""], "DOCUMENT_EMPTY"),
                            (["Alpha", ""], "PDF_PARTIAL_TEXT")):
            with self.subTest(code=code):
                with self.assertRaises(DocumentExtractionError) as caught:
                    extract_document("PDF", sample_pdf(pages))
                self.assertEqual(caught.exception.code, code)

    def test_pdf_rejects_page_count_and_text_limit(self):
        for payload, code in ((sample_pdf([""] * 101), "PDF_TOO_MANY_PAGES"),
                              (sample_pdf(["A" * 100001]), "DOCUMENT_TEXT_TOO_LONG")):
            with self.subTest(code=code):
                with self.assertRaises(DocumentExtractionError) as caught:
                    extract_document("PDF", payload)
                self.assertEqual(caught.exception.code, code)

    def test_pdf_maps_worker_timeout_to_safe_code(self):
        import subprocess

        with patch("agentfit_ai.document_extraction.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("pdf-worker", 15)):
            with self.assertRaises(DocumentExtractionError) as caught:
                extract_document("PDF", sample_pdf(["Alpha"]))
        self.assertEqual(caught.exception.code, "PDF_TIMEOUT")

    def test_pdf_rejects_malformed_worker_error_instead_of_raising_type_error(self):
        completed = CompletedProcess([], 0, stdout=b'{"error": []}')
        with patch("agentfit_ai.document_extraction.subprocess.run",
                   return_value=completed):
            with self.assertRaises(DocumentExtractionError) as caught:
                extract_document("PDF", sample_pdf(["Alpha"]))
        self.assertEqual(caught.exception.code, "PDF_WORKER_FAILED")

    def test_pdf_rejects_non_utf8_worker_text(self):
        completed = CompletedProcess(
            [], 0,
            stdout=(b'{"text": "\\ud800", "page_count": 1, '
                    b'"page_spans": [{"page": 1, "start": 0, "end": 1}]}'))
        with patch("agentfit_ai.document_extraction.subprocess.run",
                   return_value=completed):
            with self.assertRaises(DocumentExtractionError) as caught:
                extract_document("PDF", sample_pdf(["Alpha"]))
        self.assertEqual(caught.exception.code, "PDF_WORKER_FAILED")

    def test_pdf_accepts_maximum_supplementary_unicode_worker_output(self):
        text = "😀" * 100000
        output = json.dumps({"text": text, "page_count": 1,
                             "page_spans": [{"page": 1, "start": 0,
                                             "end": 100000}]}).encode("ascii")
        self.assertGreater(len(output), 1000000)
        completed = CompletedProcess([], 0, stdout=output)
        with patch("agentfit_ai.document_extraction.subprocess.run",
                   return_value=completed):
            result = extract_document("PDF", sample_pdf(["Alpha"]))
        self.assertEqual(result.character_count, 100000)


if __name__ == "__main__":
    unittest.main()
