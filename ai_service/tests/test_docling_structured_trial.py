"""Fail-closed PDF structure and page-offset checks for optional Docling."""

import importlib.util
from types import SimpleNamespace
import unittest

from agentfit_ai.document_extraction import DocumentExtractionError

try:
    from agentfit_ai.docling_structured_trial import convert_structured_pdf_bytes
except ImportError:
    convert_structured_pdf_bytes = None


def text_item(text, page, label="paragraph"):
    return SimpleNamespace(text=text, prov=[SimpleNamespace(page_no=page)],
                           label=SimpleNamespace(value=label))


def table_item(cells, page):
    return SimpleNamespace(
        data=SimpleNamespace(table_cells=[SimpleNamespace(text=value)
                                               for value in cells]),
        prov=[SimpleNamespace(page_no=page)],
        label=SimpleNamespace(value="table"))


class FakeDocument:
    def __init__(self, page_texts, items):
        self.pages = {number: object() for number in page_texts}
        self.page_texts = page_texts
        self.items = items
        self.tables = [item for item in items if hasattr(item, "data")]

    def export_to_text(self, *, page_no, traverse_pictures):
        if not traverse_pictures:
            raise AssertionError("picture text must be traversed")
        return self.page_texts[page_no]

    def iterate_items(self, *, traverse_pictures):
        if not traverse_pictures:
            raise AssertionError("picture text must be traversed")
        return iter((item, 0) for item in self.items)


class FakeConverter:
    def __init__(self, document, status="success"):
        self.document = document
        self.status = status

    def convert(self, stream):
        return SimpleNamespace(status=SimpleNamespace(value=self.status),
                               document=self.document)


class DoclingStructuredTrialTests(unittest.TestCase):
    def test_heading_table_and_unicode_offsets_are_preserved(self):
        self.assertIsNotNone(convert_structured_pdf_bytes)
        document = FakeDocument(
            {1: "제목\n가😀", 2: "항목 값"},
            [text_item("제목", 1, "title"), text_item("가😀", 1),
             table_item(["항목", "값"], 2)])
        result = convert_structured_pdf_bytes(
            b"%PDF-synthetic", converter=FakeConverter(document))
        self.assertEqual(result.extracted.text, "제목\n가😀\n항목 값")
        self.assertEqual(result.extracted.page_spans, [
            {"page": 1, "start": 0, "end": 5},
            {"page": 2, "start": 6, "end": 10}])
        self.assertEqual((result.heading_count, result.table_count), (1, 1))

    def test_missing_table_cell_fails_whole_document(self):
        document = FakeDocument({1: "항목"}, [table_item(["항목", "빠진값"], 1)])
        with self.assertRaises(DocumentExtractionError) as caught:
            convert_structured_pdf_bytes(
                b"%PDF-synthetic", converter=FakeConverter(document))
        self.assertEqual(caught.exception.code, "PDF_PARTIAL_TEXT")

    def test_missing_heading_fails_whole_document(self):
        document = FakeDocument({1: "본문"}, [text_item("제목", 1, "title"),
                                          text_item("본문", 1)])
        with self.assertRaises(DocumentExtractionError) as caught:
            convert_structured_pdf_bytes(
                b"%PDF-synthetic", converter=FakeConverter(document))
        self.assertEqual(caught.exception.code, "PDF_PARTIAL_TEXT")

    def test_repeated_body_item_cannot_be_collapsed_to_one_occurrence(self):
        document = FakeDocument({1: "CedarDB"},
                                [text_item("CedarDB", 1),
                                 text_item("CedarDB", 1)])
        with self.assertRaises(DocumentExtractionError) as caught:
            convert_structured_pdf_bytes(
                b"%PDF-synthetic", converter=FakeConverter(document))
        self.assertEqual(caught.exception.code, "PDF_PARTIAL_TEXT")

    def test_missing_page_or_multisource_item_fails_closed(self):
        for document in (
            FakeDocument({1: "본문", 2: ""}, [text_item("본문", 1)]),
            FakeDocument({1: "본문"}, [SimpleNamespace(
                text="본문", prov=[SimpleNamespace(page_no=1),
                                  SimpleNamespace(page_no=2)],
                label=SimpleNamespace(value="paragraph"))])):
            with self.subTest(document=document):
                with self.assertRaises(DocumentExtractionError):
                    convert_structured_pdf_bytes(
                        b"%PDF-synthetic", converter=FakeConverter(document))

    def test_partial_conversion_does_not_return_partial_text(self):
        document = FakeDocument({1: "본문"}, [text_item("본문", 1)])
        with self.assertRaises(DocumentExtractionError) as caught:
            convert_structured_pdf_bytes(
                b"%PDF-synthetic", converter=FakeConverter(
                    document, status="partial_success"))
        self.assertEqual(caught.exception.code, "PDF_WORKER_FAILED")

    @unittest.skipUnless(importlib.util.find_spec("docling"),
                         "optional standard Docling dependency unavailable")
    def test_real_standard_pipeline_converts_two_page_synthetic_pdf(self):
        from tests.test_document_extraction import sample_pdf

        result = convert_structured_pdf_bytes(sample_pdf(["Alpha", "Beta"]))
        self.assertEqual(result.extracted.page_count, 2)
        self.assertIn("Alpha", result.extracted.text)
        self.assertIn("Beta", result.extracted.text)
        self.assertEqual(result.table_count, 0)

    @unittest.skipUnless(importlib.util.find_spec("docling") and
                         importlib.util.find_spec("reportlab"),
                         "optional Docling PDF fixture dependencies unavailable")
    def test_real_standard_pipeline_preserves_table_cells_and_heading(self):
        from io import BytesIO
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas
        from reportlab.platypus import Table, TableStyle

        output = BytesIO()
        page = canvas.Canvas(output)
        page.setFont("Helvetica-Bold", 18)
        page.drawString(72, 760, "System Proposal")
        table = Table([["Feature", "Status"], ["Search", "Confirmed"],
                       ["Export", "Proposed"]], colWidths=[140, 140],
                      rowHeights=[28, 28, 28])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
        table.wrapOn(page, 300, 300)
        table.drawOn(page, 72, 600)
        page.showPage()
        page.save()

        result = convert_structured_pdf_bytes(output.getvalue())
        self.assertEqual(result.heading_count, 1)
        self.assertEqual(result.table_count, 1)
        self.assertTrue(all(value in result.extracted.text
                            for value in ("Search", "Confirmed", "Export", "Proposed")))


if __name__ == "__main__":
    unittest.main()
