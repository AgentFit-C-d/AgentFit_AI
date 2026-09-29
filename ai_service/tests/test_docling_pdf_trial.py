import unittest
from types import SimpleNamespace

from agentfit_ai.docling_pdf_trial import convert_docling_pdf_bytes
from agentfit_ai.document_extraction import DocumentExtractionError


def fake_result(pages, texts, status="success", tables=None):
    items = [SimpleNamespace(text=text, prov=[SimpleNamespace(page_no=page)])
             for page, text in texts]
    return SimpleNamespace(status=SimpleNamespace(value=status),
                           document=SimpleNamespace(pages={n: object() for n in pages},
                                                    texts=items, tables=tables or []))


class FakeConverter:
    def __init__(self, result):
        self.result = result

    def convert(self, stream):
        return self.result


class DoclingPdfTrialTests(unittest.TestCase):
    def test_page_offsets_follow_canonical_text(self):
        result = convert_docling_pdf_bytes(
            b"%PDF-synthetic", converter=FakeConverter(fake_result(
                [1, 2], [(1, "Alpha"), (2, "Beta")])))
        self.assertEqual(result.text, "Alpha\nBeta")
        self.assertEqual(result.page_spans, [
            {"page": 1, "start": 0, "end": 5},
            {"page": 2, "start": 6, "end": 10}])
        self.assertEqual(result.page_count, 2)

    def test_page_offsets_count_unicode_codepoints(self):
        result = convert_docling_pdf_bytes(
            b"%PDF-synthetic", converter=FakeConverter(fake_result(
                [1, 2], [(1, "가😀"), (2, "나")])))
        self.assertEqual(result.page_spans[1], {"page": 2, "start": 3, "end": 4})
        self.assertEqual(result.text[result.page_spans[1]["start"]:], "나")

    def test_missing_page_and_failed_conversion_do_not_return_partial_text(self):
        for result in (fake_result([1, 2], [(1, "Alpha")]),
                       fake_result([1], [(1, "Alpha")], status="failure")):
            with self.subTest(result=result.status.value):
                with self.assertRaises(DocumentExtractionError):
                    convert_docling_pdf_bytes(b"%PDF-synthetic",
                                              converter=FakeConverter(result))

    def test_invalid_pdf_is_rejected_before_converter(self):
        with self.assertRaises(DocumentExtractionError) as caught:
            convert_docling_pdf_bytes(b"not a PDF", converter=FakeConverter(None))
        self.assertEqual(caught.exception.code, "PDF_INVALID")

    def test_separate_table_collection_cannot_be_silently_dropped(self):
        result = fake_result([1], [(1, "Summary")], tables=[object()])
        with self.assertRaises(DocumentExtractionError) as caught:
            convert_docling_pdf_bytes(b"%PDF-synthetic", converter=FakeConverter(result))
        self.assertEqual(caught.exception.code, "PDF_PARTIAL_TEXT")


if __name__ == "__main__":
    unittest.main()
