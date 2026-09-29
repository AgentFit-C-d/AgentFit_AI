"""Synthetic-only PDF -> Docling -> LangExtract -> rule evaluation."""

import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path

from .docling_pdf_trial import convert_docling_pdf_bytes
from .docling_structured_trial import StructuredDocument, convert_structured_pdf_bytes
from .document_extraction import DocumentExtractionError, extract_document
from .false_complete_evaluation import write_safe_json
from .langextract_solar_trial import extract_candidates, load_key, score_case


CASES_PATH = (Path(__file__).resolve().parents[2] /
              "specs/ai-developer/04-analysis-provider/"
              "docling-structured-grounding-evaluation/heldout-cases.json")
CASES_SHA256 = "827bcd481eb4a5b8963c60e0961ae40df18dfacf400b77ac0d6b7348ba862a1e"
_SAFE_PDF_ERRORS = frozenset((
    "PDF_INVALID", "PDF_LOCKED", "PDF_TOO_MANY_PAGES", "PDF_PARTIAL_TEXT",
    "PDF_TIMEOUT", "PDF_WORKER_FAILED", "DOCUMENT_TOO_LARGE",
    "DOCUMENT_TEXT_TOO_LONG", "DOCUMENT_EMPTY"))


def load_cases() -> list[dict]:
    fixture = CASES_PATH.read_bytes()
    if hashlib.sha256(fixture).hexdigest() != CASES_SHA256:
        raise ValueError("pinned cases hash mismatch")
    data = json.loads(fixture.decode("utf-8"))
    cases = data.get("cases")
    if (data.get("version") != "docling-grounding-heldout-v1" or
            type(cases) is not list or len(cases) != 12 or
            Counter(case.get("category") for case in cases) !=
            {"repeat": 4, "negation": 4, "proposal": 4} or
            len({case.get("id") for case in cases}) != 12):
        raise ValueError("invalid pinned cases")
    for case in cases:
        if (type(case) is not dict or
                set(case) != {"id", "category", "lines", "anchor", "quote",
                              "field", "state", "expected_decision"} or
                type(case["id"]) is not str or
                type(case["lines"]) is not list or not case["lines"] or
                any(type(line) is not str or not line.strip()
                    for line in case["lines"]) or
                type(case["anchor"]) is not str or
                type(case["quote"]) is not str or
                case["anchor"].count(case["quote"]) != 1 or
                case["field"] not in ("database", "features") or
                case["state"] != "present" or
                case["expected_decision"] not in ("allow", "review")):
            raise ValueError("invalid pinned cases")
    return cases


def render_synthetic_pdf(lines: list[str]) -> bytes:
    """Render only fixed synthetic Korean lines in memory."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    output = BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    page = canvas.Canvas(output)
    page.setFont("HYGothic-Medium", 12)
    for index, line in enumerate(lines):
        page.drawString(72, 760 - 24 * index, line)
    page.showPage()
    page.save()
    return output.getvalue()


def _pypdf_converter(raw: bytes) -> StructuredDocument:
    return StructuredDocument(extract_document("PDF", raw), 0, 0)


def _native_converter(raw: bytes) -> StructuredDocument:
    return StructuredDocument(convert_docling_pdf_bytes(raw), 0, 0)


def locate_gold(extracted, anchor: str, quote: str) -> tuple[int, int, int]:
    text = extracted.text
    def unique_start(source: str, fragment: str) -> int | None:
        start = source.find(fragment)
        return (start if start >= 0 and
                source.find(fragment, start + 1) < 0 else None)

    anchor_start = (unique_start(text, anchor) if type(anchor) is str and anchor
                    else None)
    quote_start = (unique_start(anchor, quote)
                   if type(quote) is str and quote and anchor_start is not None
                   else None)
    if (type(anchor) is not str or not anchor or
            type(quote) is not str or not quote or
            anchor_start is None or quote_start is None):
        raise ValueError("ambiguous gold source")
    start = anchor_start + quote_start
    end = start + len(quote)
    pages = [span["page"] for span in extracted.page_spans
             if span["start"] <= start < end <= span["end"]]
    if len(pages) != 1:
        raise ValueError("gold crosses page boundary")
    return start, end, pages[0]


def evaluate_cases(cases: list[dict], key: str, *,
                   converter=convert_structured_pdf_bytes,
                   extractor=extract_candidates,
                   renderer=render_synthetic_pdf) -> dict:
    """One PDF conversion and model call per unique synthetic document."""
    pdf_cache, model_cache = {}, {}
    rows = []
    for case in cases:
        source_id = tuple(case["lines"])
        if source_id not in pdf_cache:
            try:
                pdf_cache[source_id] = converter(renderer(case["lines"]))
            except DocumentExtractionError as error:
                pdf_cache[source_id] = {"error": (
                    error.code if error.code in _SAFE_PDF_ERRORS
                    else "PDF_WORKER_FAILED")}
            except Exception:
                pdf_cache[source_id] = {"error": "PDF_WORKER_FAILED"}
        converted = pdf_cache[source_id]
        row = {"case_id": case["id"], "category": case["category"]}
        if type(converted) is dict:
            row.update(outcome="failed", error=converted["error"])
        else:
            document = converted.extracted
            try:
                start, end, page = locate_gold(document, case["anchor"],
                                               case["quote"])
            except ValueError:
                row.update(outcome="failed", error="GOLD_MAPPING_FAILED")
            else:
                if source_id not in model_cache:
                    try:
                        model_cache[source_id] = extractor(document.text, key)
                    except Exception:
                        model_cache[source_id] = {"error": "MODEL_FAILED"}
                extracted = model_cache[source_id]
                if type(extracted) is dict:
                    row.update(outcome="failed", error=extracted["error"])
                else:
                    try:
                        scored = score_case({
                            "id": case["id"], "document": document.text,
                            "candidate": {"field": case["field"],
                                          "state": case["state"],
                                          "start": start, "end": end},
                            "expected_decision": case["expected_decision"]},
                            extracted)
                    except Exception:
                        row.update(outcome="failed", error="SCORING_FAILED")
                    else:
                        row.update(scored)
                        row.update(outcome="completed", page=page)
        rows.append(row)
    completed = [row for row in rows if row["outcome"] == "completed"]
    return {"version": "docling-grounding-heldout-v1", "total": len(rows),
            "completed": len(completed), "failed": len(rows) - len(completed),
            "input_conversions": len(pdf_cache), "provider_calls": len(model_cache),
            "false_auto_confirmations": sum(
                row["false_auto_confirmation"] for row in completed),
            "missed_allows": sum(row["missed_allow"] for row in completed),
            "exact_gold_positions": sum(row["evidence_exact"] for row in completed),
            "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic-only Docling grounding evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--input-path", choices=("docling", "native", "pypdf"),
                        default="docling")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    if args.output.exists():
        parser.error("output already exists")
    try:
        cases = load_cases()
    except (OSError, ValueError, UnicodeError):
        parser.error("pinned cases invalid")
    key = load_key(args.env_file)
    converter = {"docling": convert_structured_pdf_bytes,
                 "native": _native_converter,
                 "pypdf": _pypdf_converter}[args.input_path]
    result = evaluate_cases(cases, key, converter=converter)
    result["input_path"] = args.input_path
    forbidden = tuple(value for case in cases for value in
                      (*case["lines"], case["anchor"], case["quote"])) + (key,)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_safe_json(args.output, result, forbidden_strings=forbidden)
    print(json.dumps({name: result[name] for name in (
        "total", "completed", "failed", "input_conversions", "provider_calls",
        "false_auto_confirmations", "missed_allows", "exact_gold_positions")}))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
