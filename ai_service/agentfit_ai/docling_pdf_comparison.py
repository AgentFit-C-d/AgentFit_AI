"""Source-free diagnostic metrics for three local PDF extraction paths."""

from collections import Counter
from time import monotonic
import re

from .docling_pdf_trial import convert_docling_pdf_bytes
from .docling_structured_trial import StructuredDocument, convert_structured_pdf_bytes
from .document_extraction import (DocumentExtractionError, ExtractedDocument,
                                  extract_document)


_SAFE_ERRORS = frozenset((
    "DOCUMENT_TOO_LARGE", "DOCUMENT_TEXT_TOO_LONG", "DOCUMENT_EMPTY",
    "PDF_INVALID", "PDF_LOCKED", "PDF_TOO_MANY_PAGES", "PDF_PARTIAL_TEXT",
    "PDF_TIMEOUT", "PDF_WORKER_FAILED"))


def _tokens(text: str) -> Counter:
    return Counter(re.findall(r"\w+", text.casefold()))


def _coverage(source: str, target: str) -> float:
    source_counts, target_counts = _tokens(source), _tokens(target)
    count = sum(source_counts.values())
    return round(sum(min(amount, target_counts[token])
                     for token, amount in source_counts.items()) / count, 4) if count else 0.0


def compare_pdf_bytes(raw: bytes, *, pypdf_extractor=None,
                      native_extractor=convert_docling_pdf_bytes,
                      structured_extractor=convert_structured_pdf_bytes) -> dict:
    """Compare extraction paths without returning source text or exception details."""
    if pypdf_extractor is None:
        pypdf_extractor = lambda content: extract_document("PDF", content)
    extractors = (("pypdf", pypdf_extractor), ("native", native_extractor),
                  ("standard", structured_extractor))
    report = {}
    documents = {}
    for name, extractor in extractors:
        started = monotonic()
        try:
            result = extractor(raw)
            document = result.extracted if name == "standard" else result
            if (type(document) is not ExtractedDocument or
                    (name == "standard" and type(result) is not StructuredDocument)):
                raise ValueError("invalid extractor result")
        except DocumentExtractionError as error:
            report[name] = {"status": "failed", "error": (
                error.code if error.code in _SAFE_ERRORS else "EXTRACTION_FAILED")}
            continue
        except Exception:
            report[name] = {"status": "failed", "error": "EXTRACTION_FAILED"}
            continue
        documents[name] = document
        report[name] = {"status": "completed", "pages": document.page_count,
                        "characters": document.character_count,
                        "seconds": round(monotonic() - started, 3)}
        if name == "standard":
            report[name]["headings"] = result.heading_count
            report[name]["tables"] = result.table_count
    if "standard" in documents and "pypdf" in documents:
        standard = documents["standard"].text
        report["comparison"] = {
            "status": "completed",
            "pypdf_tokens_in_standard": _coverage(documents["pypdf"].text, standard),
        }
        if "native" in documents:
            report["comparison"]["native_tokens_in_standard"] = _coverage(
                documents["native"].text, standard)
    else:
        report["comparison"] = {"status": "not_evaluated"}
    return report
