"""Synthetic-only scoring of every extracted candidate in a PDF document."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .anchored_grounding import ground_anchored_extractions
from .document_grounding_rules import guard_candidate
from .document_extraction import DocumentExtractionError
from .docling_grounding_evaluation import (
    _SAFE_PDF_ERRORS, _native_converter, _pypdf_converter,
    classify_candidate_mentions, locate_gold, render_structured_pdf,
    render_synthetic_pdf)
from .docling_structured_trial import convert_structured_pdf_bytes
from .false_complete_evaluation import write_safe_json
from .langextract_solar_trial import extract_candidates, load_key


_FIELDS = frozenset(("database", "features"))
_STATUSES = frozenset(("confirmed", "negated", "tentative", "irrelevant"))
CASES_PATH = (Path(__file__).resolve().parents[2] /
              "specs/ai-developer/04-analysis-provider/"
              "full-candidate-grounding-evaluation/cases.json")
CASES_SHA256 = "d6bf2dfbdf02fbd1a3892a834cd72a4d64eaf867c7b92459c768fa04021b4e99"


def load_cases() -> list[dict]:
    fixture = CASES_PATH.read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(fixture).hexdigest() != CASES_SHA256:
        raise ValueError("pinned cases hash mismatch")
    data = json.loads(fixture.decode("utf-8"))
    cases = data.get("documents")
    if (data.get("version") != "full-candidate-grounding-v1" or
            type(cases) is not list or len(cases) != 4 or
            Counter(case.get("category") for case in cases) !=
            {"repeat": 1, "negation": 1, "proposal": 1, "structured": 1} or
            len({case.get("id") for case in cases}) != 4):
        raise ValueError("invalid pinned cases")
    for case in cases:
        if (type(case) is not dict or
                set(case) != {"id", "category", "layout", "lines", "expected"} or
                type(case["id"]) is not str or not case["id"] or
                case["layout"] not in ("plain", "structured") or
                type(case["lines"]) is not list or not case["lines"] or
                any(type(line) is not str or not line.strip()
                    for line in case["lines"]) or
                type(case["expected"]) is not list or not case["expected"]):
            raise ValueError("invalid pinned cases")
        for item in case["expected"]:
            if (type(item) is not dict or
                    set(item) != {"anchor", "quote", "field"} or
                    type(item["anchor"]) is not str or not item["anchor"] or
                    type(item["quote"]) is not str or not item["quote"] or
                    item["anchor"].count(item["quote"]) != 1 or
                    item["field"] not in _FIELDS):
                raise ValueError("invalid pinned gold")
    return cases


def _page_for(document, start: int, end: int) -> int | None:
    pages = [span["page"] for span in document.page_spans
             if span["start"] <= start < end <= span["end"]]
    return pages[0] if len(pages) == 1 else None


def score_document(document, extractions: list, labels: list[dict],
                   gold: list[dict]) -> dict:
    """Count off-target allows and missing gold without returning source text."""
    if (type(extractions) is not list or type(labels) is not list or
            type(gold) is not list or len(labels) != len(extractions)):
        raise ValueError("invalid evaluation inputs")
    text = document.text
    gold_pairs = set()
    for item in gold:
        if (type(item) is not dict or set(item) != {"start", "end", "field", "page"} or
                item["field"] not in _FIELDS or
                type(item["start"]) is not int or type(item["end"]) is not int or
                _page_for(document, item["start"], item["end"]) != item["page"]):
            raise ValueError("invalid gold")
        pair = (item["start"], item["end"], item["field"])
        if pair in gold_pairs:
            raise ValueError("duplicate gold")
        gold_pairs.add(pair)
    for label in labels:
        if (type(label) is not dict or set(label) != {"field", "status"} or
                label["field"] not in (*_FIELDS, "other") or
                label["status"] not in _STATUSES):
            raise ValueError("invalid candidate labels")
    aligned = ground_anchored_extractions(text, extractions)
    if len(aligned) != len(labels):
        raise ValueError("incomplete alignment")
    exact_spans = Counter((row["start"], row["end"])
                          for row in aligned if row["status"] == "exact")
    allowed = []
    for row, label in zip(aligned, labels):
        if row["status"] != "exact" or label["field"] not in _FIELDS or \
                label["status"] != "confirmed":
            continue
        start, end = row["start"], row["end"]
        if exact_spans[(start, end)] != 1 or _page_for(document, start, end) is None:
            continue
        if guard_candidate(text, field=label["field"], state="present",
                           start=start, end=end) == "allow":
            allowed.append((start, end, label["field"]))
    accepted = set(allowed)
    missed_reasons = Counter()
    for start, end, field in gold_pairs - accepted:
        matches = [(row, label) for row, label in zip(aligned, labels)
                   if row["status"] == "exact" and
                   (row["start"], row["end"]) == (start, end)]
        if not matches:
            reason = "candidate_missing"
        elif not any(label["field"] == field for _, label in matches):
            reason = "field_mismatch"
        elif not any(label["field"] == field and
                     label["status"] == "confirmed" for _, label in matches):
            reason = "status_not_confirmed"
        elif exact_spans[(start, end)] != 1:
            reason = "duplicate_or_ambiguous"
        else:
            reason = "rule_blocked"
        missed_reasons[reason] += 1
    return {"candidate_count": len(extractions),
            "exact_candidate_positions": sum(row["status"] == "exact"
                                             for row in aligned),
            "allowed_candidates": len(allowed),
            "exact_allowed_positions": len(allowed),
            "false_auto_confirmations": sum(pair not in gold_pairs
                                            for pair in allowed),
            "missed_allows": len(gold_pairs - accepted),
            "missed_reasons": dict(missed_reasons),
            "gold_allows": len(gold_pairs)}


def evaluate_documents(cases: list[dict], key: str, *,
                       converter=convert_structured_pdf_bytes,
                       extractor=extract_candidates,
                       classifier=classify_candidate_mentions,
                       plain_renderer=render_synthetic_pdf,
                       structured_renderer=render_structured_pdf) -> dict:
    """Run whole-document evaluation without returning source or model text."""
    rows = []
    extraction_calls = classification_calls = 0
    for case in cases:
        row = {"case_id": case["id"], "category": case["category"]}
        try:
            renderer = (structured_renderer if case["layout"] == "structured"
                        else plain_renderer)
            converted = converter(renderer(case["lines"]))
        except DocumentExtractionError as error:
            row.update(outcome="failed", error=(
                error.code if error.code in _SAFE_PDF_ERRORS
                else "PDF_WORKER_FAILED"))
        except Exception:
            row.update(outcome="failed", error="PDF_WORKER_FAILED")
        else:
            document = converted.extracted
            try:
                gold = []
                for item in case["expected"]:
                    start, end, page = locate_gold(
                        document, item["anchor"], item["quote"])
                    gold.append({"start": start, "end": end,
                                 "field": item["field"], "page": page})
                if len({(item["start"], item["end"], item["field"])
                        for item in gold}) != len(gold):
                    raise ValueError("duplicate gold")
            except ValueError:
                row.update(outcome="failed", error="GOLD_MAPPING_FAILED")
            else:
                extraction_calls += 1
                try:
                    extractions = list(extractor(document.text, key))
                except Exception:
                    row.update(outcome="failed", error="MODEL_FAILED")
                else:
                    if extractions:
                        classification_calls += 1
                    try:
                        labels = classifier(document.text, extractions, key)
                    except Exception:
                        row.update(outcome="failed", error="CLASSIFICATION_FAILED")
                    else:
                        try:
                            scored = score_document(document, extractions,
                                                    labels, gold)
                        except Exception:
                            row.update(outcome="failed", error="SCORING_FAILED")
                        else:
                            row.update(scored)
                            row.update(outcome="completed", page_count=document.page_count,
                                       heading_count=converted.heading_count,
                                       table_count=converted.table_count)
        rows.append(row)
    completed = [row for row in rows if row["outcome"] == "completed"]
    missed_reasons = Counter()
    for row in completed:
        missed_reasons.update(row["missed_reasons"])
    return {"version": "full-candidate-grounding-v1", "total": len(rows),
            "completed": len(completed), "failed": len(rows)-len(completed),
            "extraction_calls": extraction_calls,
            "classification_calls": classification_calls,
            "provider_calls": extraction_calls+classification_calls,
            "candidate_count": sum(row["candidate_count"] for row in completed),
            "gold_allows": sum(row["gold_allows"] for row in completed),
            "allowed_candidates": sum(row["allowed_candidates"] for row in completed),
            "false_auto_confirmations": sum(
                row["false_auto_confirmations"] for row in completed),
            "missed_allows": sum(row["missed_allows"] for row in completed),
            "missed_reasons": dict(missed_reasons),
            "exact_allowed_positions": sum(
                row["exact_allowed_positions"] for row in completed),
            "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic-only full-candidate PDF grounding evaluation")
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
    result = evaluate_documents(cases, key, converter=converter)
    result["input_path"] = args.input_path
    forbidden = tuple(value for case in cases for value in (
        *case["lines"], *(item["anchor"] for item in case["expected"]),
        *(item["quote"] for item in case["expected"]))) + (key,)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_safe_json(args.output, result, forbidden_strings=forbidden)
    print(json.dumps({name: result[name] for name in (
        "total", "completed", "failed", "candidate_count", "gold_allows",
        "allowed_candidates", "false_auto_confirmations", "missed_allows",
        "provider_calls")}))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
