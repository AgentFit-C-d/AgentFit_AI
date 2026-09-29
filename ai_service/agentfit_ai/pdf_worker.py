"""Child process for extracting PDF text without writing source files."""

import json
import sys
from io import BytesIO

from .worker_memory import apply_pdf_memory_limit


MAX_FILE_BYTES = 10_485_760
MAX_PAGES = 100
MAX_TEXT_POINTS = 100_000


def extract_pdf_bytes(raw: bytes) -> dict:
    if len(raw) > MAX_FILE_BYTES:
        return {"error": "DOCUMENT_TOO_LARGE"}
    if not raw.startswith(b"%PDF-"):
        return {"error": "PDF_INVALID"}
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted:
            return {"error": "PDF_LOCKED"}
        page_count = len(reader.pages)
        if page_count > MAX_PAGES:
            return {"error": "PDF_TOO_MANY_PAGES"}
        if page_count == 0:
            return {"error": "DOCUMENT_EMPTY"}
        texts = []
        spans = []
        total = 0
        for number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if type(page_text) is not str:
                return {"error": "PDF_INVALID"}
            if texts:
                total += 1
            start = total
            total += len(page_text)
            if total > MAX_TEXT_POINTS:
                return {"error": "DOCUMENT_TEXT_TOO_LONG"}
            texts.append(page_text)
            spans.append({"page": number, "start": start, "end": total})
        if not any(text.strip() for text in texts):
            return {"error": "DOCUMENT_EMPTY"}
        if any(not text.strip() for text in texts):
            return {"error": "PDF_PARTIAL_TEXT"}
        return {"text": "\n".join(texts), "page_count": page_count,
                "page_spans": spans}
    except MemoryError:
        return {"error": "PDF_WORKER_FAILED"}
    except Exception:
        return {"error": "PDF_INVALID"}


def main() -> int:
    try:
        apply_pdf_memory_limit()
    except Exception:
        sys.stdout.buffer.write(b'{"error": "PDF_WORKER_FAILED"}')
        return 0
    raw = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
    result = extract_pdf_bytes(raw)
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True).encode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
