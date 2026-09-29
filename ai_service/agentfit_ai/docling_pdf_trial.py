"""Offline Docling native PDF trial; intentionally outside the service worker."""

from io import BytesIO

from .document_extraction import (DocumentExtractionError, ExtractedDocument,
                                  MAX_FILE_BYTES, MAX_TEXT_POINTS)


def convert_docling_pdf_bytes(raw: bytes, *, converter=None) -> ExtractedDocument:
    if type(raw) is not bytes or not raw.startswith(b"%PDF-"):
        raise DocumentExtractionError("PDF_INVALID")
    if len(raw) > MAX_FILE_BYTES:
        raise DocumentExtractionError("DOCUMENT_TOO_LARGE")
    try:
        if converter is None:
            from docling.datamodel.base_models import DocumentStream, InputFormat
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.pipeline.native_pdf_pipeline import NativePdfPipeline

            converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=NativePdfPipeline)})
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
    texts = getattr(document, "texts", None)
    tables = getattr(document, "tables", None)
    if tables:
        raise DocumentExtractionError("PDF_PARTIAL_TEXT")
    if (type(pages) is not dict or not 1 <= len(pages) <= 100 or
            set(pages) != set(range(1, len(pages) + 1)) or
            type(texts) is not list):
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    per_page = {number: [] for number in pages}
    for item in texts:
        text, provenance = getattr(item, "text", None), getattr(item, "prov", None)
        if (type(text) is not str or not text.strip() or
                type(provenance) is not list or len(provenance) != 1 or
                getattr(provenance[0], "page_no", None) not in per_page):
            raise DocumentExtractionError("PDF_WORKER_FAILED")
        per_page[provenance[0].page_no].append(text)
    if any(not parts for parts in per_page.values()):
        raise DocumentExtractionError("PDF_PARTIAL_TEXT")
    page_texts = ["\n".join(per_page[number]) for number in range(1, len(pages) + 1)]
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
    return ExtractedDocument("PDF", text, len(raw), len(text), len(pages), spans)
