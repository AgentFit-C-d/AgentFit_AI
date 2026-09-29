"""Optional local standard-Docling PDF conversion with exact page offsets."""

from collections import Counter
from dataclasses import dataclass
from io import BytesIO
import re

from .document_extraction import (DocumentExtractionError, ExtractedDocument,
                                  MAX_FILE_BYTES, MAX_TEXT_POINTS)


@dataclass(frozen=True)
class StructuredDocument:
    extracted: ExtractedDocument
    heading_count: int
    table_count: int


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _standard_converter():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

    options = PdfPipelineOptions(
        do_ocr=False, do_table_structure=True, enable_remote_services=False,
        document_timeout=120)
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(
            pipeline_cls=StandardPdfPipeline, pipeline_options=options)})


def convert_structured_pdf_bytes(raw: bytes, *, converter=None) -> StructuredDocument:
    """Reject partial or unmapped content instead of returning plausible text."""
    if type(raw) is not bytes or not raw.startswith(b"%PDF-"):
        raise DocumentExtractionError("PDF_INVALID")
    if len(raw) > MAX_FILE_BYTES:
        raise DocumentExtractionError("DOCUMENT_TOO_LARGE")
    try:
        if converter is None:
            from docling.datamodel.base_models import DocumentStream

            converter = _standard_converter()
            source = DocumentStream(name="trial.pdf", stream=BytesIO(raw))
        else:
            source = BytesIO(raw)
        result = converter.convert(source)
    except Exception:
        raise DocumentExtractionError("PDF_WORKER_FAILED") from None
    if getattr(getattr(result, "status", None), "value", None) != "success":
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    document = getattr(result, "document", None)
    pages = getattr(document, "pages", None)
    tables = getattr(document, "tables", None)
    if (type(pages) is not dict or not 1 <= len(pages) <= 100 or
            set(pages) != set(range(1, len(pages) + 1)) or
            type(tables) is not list):
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    try:
        page_texts = [document.export_to_text(page_no=number,
                                              traverse_pictures=True)
                      for number in range(1, len(pages) + 1)]
        items = list(document.iterate_items(traverse_pictures=True))
    except Exception:
        raise DocumentExtractionError("PDF_WORKER_FAILED") from None
    if any(type(page) is not str or not page.strip() for page in page_texts):
        raise DocumentExtractionError("PDF_PARTIAL_TEXT")
    normal_pages = [_normal(page) for page in page_texts]
    heading_count = 0
    body_tables = 0
    required_fragments = Counter()
    for item, _level in items:
        provenance = getattr(item, "prov", None)
        body_text = getattr(item, "text", None)
        table_cells = getattr(getattr(item, "data", None), "table_cells", None)
        if body_text is None and table_cells is None:
            continue
        if (type(provenance) is not list or len(provenance) != 1 or
                getattr(provenance[0], "page_no", None) not in pages):
            raise DocumentExtractionError("PDF_PARTIAL_TEXT")
        page_index = provenance[0].page_no - 1
        if body_text is not None:
            if (type(body_text) is not str or not _normal(body_text) or
                    _normal(body_text) not in normal_pages[page_index]):
                raise DocumentExtractionError("PDF_PARTIAL_TEXT")
            label = getattr(getattr(item, "label", None), "value", None)
            heading_count += label in ("title", "section_header")
            required_fragments[(page_index, _normal(body_text))] += 1
        if table_cells is not None:
            if type(table_cells) is not list:
                raise DocumentExtractionError("PDF_PARTIAL_TEXT")
            body_tables += 1
            try:
                table_markdown = item.export_to_markdown(doc=document)
            except Exception:
                raise DocumentExtractionError("PDF_PARTIAL_TEXT") from None
            if (type(table_markdown) is not str or
                    not _normal(table_markdown) or
                    _normal(table_markdown) not in normal_pages[page_index]):
                raise DocumentExtractionError("PDF_PARTIAL_TEXT")
            for cell in table_cells:
                value = getattr(cell, "text", None)
                if (type(value) is not str or
                        (_normal(value) and
                         _normal(value) not in normal_pages[page_index])):
                    raise DocumentExtractionError("PDF_PARTIAL_TEXT")
                if _normal(value):
                    required_fragments[(page_index, _normal(value))] += 1
    if any(normal_pages[page_index].count(fragment) < count
           for (page_index, fragment), count in required_fragments.items()):
        raise DocumentExtractionError("PDF_PARTIAL_TEXT")
    if body_tables != len(tables):
        raise DocumentExtractionError("PDF_PARTIAL_TEXT")
    text = "\n".join(page_texts)
    if len(text) > MAX_TEXT_POINTS:
        raise DocumentExtractionError("DOCUMENT_TEXT_TOO_LONG")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise DocumentExtractionError("PDF_WORKER_FAILED") from None
    spans = []
    offset = 0
    for number, page_text in enumerate(page_texts, start=1):
        if number > 1:
            offset += 1
        end = offset + len(page_text)
        spans.append({"page": number, "start": offset, "end": end})
        offset = end
    return StructuredDocument(
        ExtractedDocument("PDF", text, len(raw), len(text), len(pages), spans),
        heading_count, body_tables)
