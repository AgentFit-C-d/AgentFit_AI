"""One-pass public-document evaluation with source-free artifacts."""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from .diagnostics import safe_code
from .deepseek_evaluation import (NVIDIA_REVIEW_MODELS, load_key as nvidia_load_key,
                                  post_nvidia)
from .false_complete_evaluation import write_safe_json
from .line_evidence_analysis import LineEvidenceSolarAnalyzer
from .nvidia_source_selector import NvidiaSourceSelectorAnalyzer
from .source_selector_analysis import SourceSelectorSolarAnalyzer
from .public_holdout import MANIFEST, SCORE_VERSION, fetch_document, load_manifest, score_profile
from .recoverable_draft_evaluation import (CountingTransport,
                                           _structural_evidence_errors, load_key)
from .recoverable_solar_analysis import RecoverableSolarAnalyzer
from .semantic_review import REVIEW_INVALID_REASONS
from .solar import AnalysisError, post_solar_inline, safe_evidence_failure


ROOT = Path(__file__).resolve().parents[2]
_STAGES = frozenset({"core", "features", "repair", "semantic_review",
                     "semantic_repair", "semantic_recheck"})
_OUTCOMES = frozenset({"started", "failed", "validated",
                       "validation_failed", "semantic_failed"})


def _safe_validation(item):
    if type(item) is not dict:
        return None
    error = AnalysisError(item.get("code"), item.get("field"))
    error.detail = item.get("detail")
    return safe_evidence_failure(error)


class _SafeTraceMixin:
    """Capture classifications in memory without retaining provider replies."""

    def _repair_correction(self, document, errors, previous):
        correction = super()._repair_correction(document, errors, previous)
        options = correction.get("evidenceOptions", {})
        self.safe_repair_option_counts = {
            "fields": len(options),
            "choices": sum(len(item["options"]) for item in options.values()),
        }
        return correction

    def _save_diagnostic(self, diagnostic, raw_responses):
        self.safe_calls = []
        for call in diagnostic["calls"]:
            validations = [_safe_validation(item)
                           for item in call.get("validation_errors", [])]
            final = call.get("validation_error")
            if type(final) is dict:
                validations.append(_safe_validation({"code": "INVALID_EVIDENCE",
                                                     "field": final.get("field"),
                                                     "detail": final}))
            row = {"call": call["call"],
                   "stage": call["stage"] if call.get("stage") in _STAGES else "unknown",
                   "outcome": (call["outcome"] if call.get("outcome") in _OUTCOMES
                               else "unknown"),
                   "error": safe_code(call["error"]) if call.get("error") else None,
                   "validation": [item for item in validations if item is not None]}
            review_error = call.get("review_error")
            if (type(review_error) is dict and
                    review_error.get("reason") in REVIEW_INVALID_REASONS):
                row["review_reason"] = review_error["reason"]
            timing = {name: call[name]
                      for name in ("request_bytes", "provider_elapsed_ms", "elapsed_ms")
                      if type(call.get(name)) is int and 0 <= call[name] <= 1_000_000_000}
            if timing:
                row["timing"] = timing
            token_usage = {label: call[name] for label, name in (
                ("limit", "max_tokens"), ("prompt", "prompt_tokens"),
                ("completion", "completion_tokens"))
                if type(call.get(name)) is int and 0 <= call[name] <= 1_000_000_000}
            if token_usage:
                row["tokens"] = token_usage
            self.safe_calls.append(row)


class SafeTraceSolarAnalyzer(_SafeTraceMixin, RecoverableSolarAnalyzer):
    pass


class SafeTraceLineEvidenceAnalyzer(_SafeTraceMixin, LineEvidenceSolarAnalyzer):
    pass


class SafeTraceSourceSelectorAnalyzer(_SafeTraceMixin, SourceSelectorSolarAnalyzer):
    pass


class SafeTraceNvidiaSourceSelectorAnalyzer(_SafeTraceMixin, NvidiaSourceSelectorAnalyzer):
    pass


def evaluate_case(case, document, analyzer, *, clock=time.monotonic,
                  provider_calls=0):
    started = clock()
    outcome = analyzer.analyze_recoverable(document, case["id"])
    if type(outcome) is not dict or outcome.get("outcome") not in (
            "complete", "needs_confirmation", "failed"):
        raise ValueError("invalid public evaluation outcome")
    row = {"id": case["id"], "outcome": outcome["outcome"],
           "score_version": SCORE_VERSION,
           "error": (safe_code(outcome["error"]) if outcome.get("error") is not None
                     else None),
           "elapsed_ms": round((clock() - started) * 1000),
           "provider_calls": provider_calls() if callable(provider_calls) else provider_calls,
           "questions": len(outcome.get("questions", [])),
           "calls": getattr(analyzer, "safe_calls", []),
           "repair_option_counts": getattr(analyzer, "safe_repair_option_counts",
                                           {"fields": 0, "choices": 0}),
           "scored": False, "structural_evidence_errors": 0,
           "total_checks": sum(len(items) for items in case["checks"].values()),
           "matched_checks": 0, "wrong_evidence_checks": 0,
           "missing_alias_checks": 0, "indeterminate_evidence_checks": 0,
           "unassessed_values": 0,
           "expected_unknown_fields": len(case.get("unknown_fields", [])),
           "unknown_fields_preserved": 0, "unknown_fields_non_null": 0}
    if outcome["outcome"] == "failed":
        return row
    profile = outcome.get("profile")
    row["structural_evidence_errors"] = _structural_evidence_errors(
        document, case["id"], profile)
    if row["structural_evidence_errors"]:
        return row
    row.update(score_profile(case, document, profile))
    row["scored"] = True
    return row


def summarize(rows, *, planned):
    counts = Counter(row["outcome"] for row in rows)
    scored = [row for row in rows if row["scored"]]
    return {
        "score_version": SCORE_VERSION,
        "planned_cases": planned, "evaluated_cases": len(rows),
        "complete_cases": counts["complete"],
        "needs_confirmation_cases": counts["needs_confirmation"],
        "failed_cases": counts["failed"],
        "scored_profiles": len(scored),
        "matched_checks": sum(row["matched_checks"] for row in scored),
        "wrong_evidence_checks": sum(row["wrong_evidence_checks"] for row in scored),
        "missing_alias_checks": sum(row["missing_alias_checks"] for row in scored),
        "indeterminate_evidence_checks": sum(
            row["indeterminate_evidence_checks"] for row in scored),
        "unassessed_values": sum(row["unassessed_values"] for row in scored),
        "expected_unknown_fields": sum(row["expected_unknown_fields"] for row in scored),
        "unknown_fields_preserved": sum(row["unknown_fields_preserved"] for row in scored),
        "unknown_fields_non_null": sum(row["unknown_fields_non_null"] for row in scored),
        "unscored_cases": len(rows) - len(scored),
        "repair_option_fields": sum(row.get("repair_option_counts", {}).get(
            "fields", 0) for row in rows),
        "repair_option_choices": sum(row.get("repair_option_counts", {}).get(
            "choices", 0) for row in rows),
        "max_provider_calls": max((row["provider_calls"] for row in rows), default=0),
        "max_elapsed_ms": max((row["elapsed_ms"] for row in rows), default=0),
        "release_gate_passed": False,
        "release_gate_note": "Public project documents and partial labels do not prove service readiness",
    }


def main():
    parser = argparse.ArgumentParser(description="Pinned public holdout evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--partition", choices=("tuning", "heldout"), default="tuning")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--repair-context-options", action="store_true")
    parser.add_argument("--parallel-first-pass", action="store_true")
    parser.add_argument("--line-evidence", action="store_true")
    parser.add_argument("--source-selector", action="store_true")
    parser.add_argument("--source-selector-model", choices=("solar-pro4", *NVIDIA_REVIEW_MODELS),
                        default="solar-pro4")
    parser.add_argument("--accuracy-first", action="store_true")
    parser.add_argument("--extended-review-window", action="store_true")
    parser.add_argument("--compact-review", action="store_true")
    parser.add_argument("--grouped-review", action="store_true")
    parser.add_argument("--compact-review-effort", choices=("medium", "low"),
                        default="medium")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    if args.output.exists():
        parser.error("output already exists")
    if args.line_evidence and args.repair_context_options:
        parser.error("line evidence does not use quote context options")
    if args.source_selector and (args.line_evidence or args.repair_context_options):
        parser.error("source selector is exclusive with other evidence modes")
    if (args.source_selector_model != "solar-pro4" or args.accuracy_first) and not args.source_selector:
        parser.error("model comparison requires source selector mode")
    if args.compact_review and not args.source_selector:
        parser.error("compact review requires source selector mode")
    if args.grouped_review and (not args.source_selector or args.compact_review):
        parser.error("grouped review requires non-compact source selector mode")
    if args.compact_review_effort != "medium" and not args.compact_review:
        parser.error("compact review effort requires compact review mode")
    if args.extended_review_window and (not args.source_selector or
                                        not args.accuracy_first or args.compact_review):
        parser.error("extended review window requires non-compact accuracy-first source selector")
    nvidia_mode = args.source_selector_model != "solar-pro4"
    if nvidia_mode and args.parallel_first_pass:
        parser.error("NVIDIA source selector requires sequential calls")
    cases = load_manifest(args.manifest, expected_partition=args.partition)
    if args.case_id:
        selected = set(args.case_id)
        if len(selected) != len(args.case_id) or not selected <= {case["id"] for case in cases}:
            parser.error("invalid case selection")
        cases = [case for case in cases if case["id"] in selected]
    documents = [(case, fetch_document(case)) for case in cases]
    key = nvidia_load_key(args.env_file) if nvidia_mode else load_key(args.env_file)
    forbidden = (key, *(document for _, document in documents))
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"model": args.source_selector_model, "score_version": SCORE_VERSION,
            "partition": args.partition,
            "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            "sources": [{"id": case["id"], "repo": case["repo"],
                         "commit": case["commit"], "path": case["path"],
                         "sha256": case["sha256"]} for case, _ in documents],
            "one_analysis_per_case": True,
            "repair_context_options": args.repair_context_options,
            "parallel_first_pass": args.parallel_first_pass,
            "line_evidence": args.line_evidence,
            "source_selector": args.source_selector,
            "compact_review": args.compact_review,
            "grouped_review": args.grouped_review,
            "compact_review_effort": args.compact_review_effort,
            "accuracy_first": args.accuracy_first,
            "extended_review_window": args.extended_review_window,
            "analysis_timeout_seconds": (600 if args.extended_review_window else
                                         300 if args.accuracy_first else 40),
            "field_call_timeout_seconds": 120 if args.accuracy_first else 40,
            "review_max_tokens": (4096 if args.compact_review or args.grouped_review else
                                  16384 if args.accuracy_first else 8192),
            "release_gate_passed": False}
    write_safe_json(args.output / "plan.json", plan, forbidden_strings=forbidden)
    rows = []
    for case, document in documents:
        transport = CountingTransport(post_nvidia if nvidia_mode else post_solar_inline)
        analyzer_type = (SafeTraceNvidiaSourceSelectorAnalyzer if nvidia_mode else
                         SafeTraceSourceSelectorAnalyzer if args.source_selector else
                         SafeTraceLineEvidenceAnalyzer if args.line_evidence else
                         SafeTraceSolarAnalyzer)
        analyzer = analyzer_type(
            key, transport=transport, model=args.source_selector_model, evidence_contract=True,
            semantic_review=True,
            analysis_timeout_seconds=(600 if args.extended_review_window else
                                      300 if args.accuracy_first else 40),
            field_call_timeout_seconds=120 if args.accuracy_first else 40,
            review_max_tokens=(4096 if args.compact_review or args.grouped_review else
                               16384 if args.accuracy_first else 8192),
            experimental_long_timeout=args.accuracy_first,
            repair_context_options=args.repair_context_options,
            parallel_first_pass=args.parallel_first_pass,
            **({"compact_review": args.compact_review,
                "compact_review_effort": args.compact_review_effort,
                "grouped_review": args.grouped_review}
               if args.source_selector else {}))
        row = evaluate_case(case, document, analyzer,
                            provider_calls=lambda: transport.calls)
        rows.append(row)
        write_safe_json(args.output / "results.json", rows,
                        forbidden_strings=forbidden)
        write_safe_json(args.output / "summary.json",
                        summarize(rows, planned=len(cases)),
                        forbidden_strings=forbidden)
        print(json.dumps({"id": row["id"], "outcome": row["outcome"],
                          "matched_checks": row["matched_checks"],
                          "elapsed_ms": row["elapsed_ms"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
