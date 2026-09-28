"""Validate one document input before sending its text to an analyzer."""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


MAX_FILE_BYTES = 10_485_760
MAX_TEXT_POINTS = 100_000
MAX_WORKER_OUTPUT_BYTES = 1_000_000
PDF_TIMEOUT_SECONDS = 15
PDF_WORKER_ERRORS = frozenset((
    "DOCUMENT_TOO_LARGE", "DOCUMENT_TEXT_TOO_LONG", "DOCUMENT_EMPTY",
    "PDF_INVALID", "PDF_LOCKED", "PDF_TOO_MANY_PAGES", "PDF_PARTIAL_TEXT",
))


class DocumentExtractionError(ValueError):
    """A source-free input or extraction error safe to map at the service edge."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExtractedDocument:
    kind: str
    text: str
    byte_size: int
    character_count: int
    page_count: int | None
    page_spans: list[dict[str, int]]


def _pdf_worker_environment() -> dict[str, str]:
    environment = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "PATH")
                   if name in os.environ}
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _extract_pdf(content: bytes, byte_size: int) -> ExtractedDocument:
    if not content.startswith(b"%PDF-"):
        raise DocumentExtractionError("PDF_INVALID")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "agentfit_ai.pdf_worker"], input=content,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parents[1],
            env=_pdf_worker_environment(), timeout=PDF_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise DocumentExtractionError("PDF_TIMEOUT") from None
    except OSError:
        raise DocumentExtractionError("PDF_WORKER_FAILED") from None
    if completed.returncode != 0 or len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES:
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    try:
        result = json.loads(completed.stdout)
    except (ValueError, UnicodeError):
        raise DocumentExtractionError("PDF_WORKER_FAILED") from None
    if type(result) is not dict:
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    if set(result) == {"error"} and result["error"] in PDF_WORKER_ERRORS:
        raise DocumentExtractionError(result["error"])
    if set(result) != {"text", "page_count", "page_spans"}:
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    text = result["text"]
    page_count = result["page_count"]
    spans = result["page_spans"]
    if (type(text) is not str or type(page_count) is not int or
            not 1 <= page_count <= 100 or type(spans) is not list or
            len(spans) != page_count or len(text) > MAX_TEXT_POINTS or
            not text.strip()):
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    end = 0
    for index, span in enumerate(spans, start=1):
        if (type(span) is not dict or set(span) != {"page", "start", "end"} or
                type(span["page"]) is not int or span["page"] != index or
                type(span["start"]) is not int or type(span["end"]) is not int or
                span["start"] != end + (index > 1) or
                not span["start"] < span["end"] <= len(text) or
                (index > 1 and text[end] != "\n")):
            raise DocumentExtractionError("PDF_WORKER_FAILED")
        end = span["end"]
    if end != len(text):
        raise DocumentExtractionError("PDF_WORKER_FAILED")
    return ExtractedDocument("PDF", text, byte_size, len(text), page_count, spans)


def extract_document(kind: str, content: bytes | str) -> ExtractedDocument:
    if kind not in ("PDF", "MARKDOWN", "TEXT"):
        raise DocumentExtractionError("INVALID_DOCUMENT_KIND")
    if kind == "TEXT":
        if type(content) is not str:
            raise DocumentExtractionError("INVALID_DOCUMENT_CONTENT")
        try:
            byte_size = len(content.encode("utf-8"))
        except UnicodeEncodeError:
            raise DocumentExtractionError("DOCUMENT_INVALID_UTF8") from None
        text = content
    else:
        if type(content) is not bytes:
            raise DocumentExtractionError("INVALID_DOCUMENT_CONTENT")
        byte_size = len(content)
        if byte_size > MAX_FILE_BYTES:
            raise DocumentExtractionError("DOCUMENT_TOO_LARGE")
        if kind == "PDF":
            return _extract_pdf(content, byte_size)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise DocumentExtractionError("DOCUMENT_INVALID_UTF8") from None
    if len(text) > MAX_TEXT_POINTS:
        raise DocumentExtractionError("DOCUMENT_TEXT_TOO_LONG")
    if not text.strip():
        raise DocumentExtractionError("DOCUMENT_EMPTY")
    return ExtractedDocument(kind, text, byte_size, len(text), None, [])
