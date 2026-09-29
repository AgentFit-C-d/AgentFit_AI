"""Opt-in candidate-first comparison over approved redacted documents."""

import argparse
from functools import partial
import hashlib
import json
from pathlib import Path
import re
import time

from .candidate_first_profile import (CandidatePipelineError,
                                      analyze_candidate_first)
from .diagnostics import safe_code
from .false_complete_evaluation import write_safe_json
from .langextract_solar_trial import load_key
from .profile import FIELDS
from .real_document_holdout import prepare_cases, score_profile, select_cases
from .solar import AnalysisError


_SAFE_REJECTION_REASONS = frozenset((
    "invalid_candidate", "invalid_anchor", "ambiguous_anchor",
    "ambiguous_source", "alignment_conflict", "duplicate_span", "source_quote_absent"))


def evaluate_cases(cases, key: str, *, runner=analyze_candidate_first) -> dict:
    rows = []
    for case in cases:
        started = time.monotonic()
        row = {"case_id": case.id, "source_sha256": case.source_sha256,
               "redacted_sha256": case.redacted_sha256,
               "characters": len(case.text), "page_count": case.page_count,
               "heading_count": case.heading_count,
               "table_count": case.table_count}
        try:
            result = runner(case.text, case.id, key)
            if (type(result) is not dict or
                    result.get("outcome") not in ("candidate_profile",
                                                  "needs_confirmation") or
                    type(result.get("candidateCount")) is not int or
                    type(result.get("rejectedCandidateCount")) is not int or
                    type(result.get("reviewIssueCount")) is not int or
                    type(result.get("unresolvedFields")) is not list or
                    any(field not in FIELDS for field in
                        result["unresolvedFields"])):
                raise ValueError("invalid candidate analysis result")
            row.update(outcome=result["outcome"],
                       candidate_count=result["candidateCount"],
                       rejected_candidate_count=result["rejectedCandidateCount"],
                       review_issue_count=result["reviewIssueCount"],
                       unresolved_fields=result["unresolvedFields"])
            reasons = result.get("rejectedReasons", {})
            if type(reasons) is dict:
                row["rejected_reasons"] = {
                    reason: count for reason, count in reasons.items()
                    if reason in _SAFE_REJECTION_REASONS and
                    type(count) is int and 0 <= count <= 100_000}
            if result["outcome"] == "candidate_profile":
                row.update(score_profile(result["profile"], case.checks))
            else:
                suggestion = score_profile(result["profile"], case.checks)
                row.update(suggestion_matched=suggestion["matched"],
                           suggestion_checked=suggestion["total"])
        except CandidatePipelineError as error:
            row.update(outcome="failed", error=error.stage)
            if error.provider_code is not None:
                row["provider_error"] = error.provider_code
            if error.detail is not None:
                row["contract_error"] = error.detail
        except AnalysisError as error:
            row.update(outcome="failed", error=safe_code(error.code))
        except Exception:
            row.update(outcome="failed", error="TRIAL_FAILURE")
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        rows.append(row)
    completed = [row for row in rows if row["outcome"] == "candidate_profile"]
    return {"total": len(rows), "complete": len(completed),
            "needs_confirmation": sum(row["outcome"] == "needs_confirmation"
                                      for row in rows),
            "failed": sum(row["outcome"] == "failed" for row in rows),
            "matched": sum(row["matched"] for row in completed),
            "checked": sum(row["total"] for row in completed),
            "suggestion_matched": sum(row.get("suggestion_matched", 0)
                                      for row in rows),
            "suggestion_checked": sum(row.get("suggestion_checked", 0)
                                      for row in rows),
            "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Approved redacted candidate-first Profile comparison")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--case-id", choices=("H01", "H02", "H03"))
    parser.add_argument("--source-occurrences", action="store_true")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    if args.output.exists():
        parser.error("output already exists")
    try:
        manifest = args.manifest.read_bytes().replace(b"\r\n", b"\n")
        if (re.fullmatch(r"[0-9a-f]{64}", args.manifest_sha256) is None or
                hashlib.sha256(manifest).hexdigest() != args.manifest_sha256):
            raise ValueError("manifest hash mismatch")
        payload = json.loads(manifest.decode("utf-8"))
        if type(payload) is not dict or set(payload) != {"cases"}:
            raise ValueError("invalid manifest")
        prepared = prepare_cases(payload["cases"])
    except Exception:
        parser.error("private document preflight failed")
    key = load_key(args.env_file)
    runner = (partial(analyze_candidate_first, source_occurrences=True)
              if args.source_occurrences else analyze_candidate_first)
    result = evaluate_cases(select_cases(prepared, args.case_id), key, runner=runner)
    result["grounding_mode"] = ("source-occurrences" if args.source_occurrences
                                else "model-anchor")
    forbidden = (key, *(case.text for case in prepared),
                 *(str(case.get("path", "")) for case in payload["cases"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_safe_json(args.output, result, forbidden_strings=forbidden)
    print(json.dumps({name: result[name] for name in
                      ("total", "complete", "needs_confirmation", "failed",
                       "matched", "checked", "suggestion_matched",
                       "suggestion_checked")}))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
