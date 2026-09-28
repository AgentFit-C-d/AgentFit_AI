"""Single-run, source-free evaluation of opt-in recoverable drafts."""

import argparse
import hashlib
import json
import statistics
import time
from collections import Counter
from pathlib import Path

from .keyed_profile_evaluation import focus_score, full_score, load_profile_cases
from .profile import FIELDS, ProfileValidationError, validate_profile
from .recoverable_analysis import RecoverableAnchoredAnalyzer
from .solar import post_solar


ROOT = Path(__file__).resolve().parents[2]
CODE_PATHS = (
    "ai_service/agentfit_ai/anchored_analysis.py",
    "ai_service/agentfit_ai/recoverable_draft.py",
    "ai_service/agentfit_ai/recoverable_judgment.py",
    "ai_service/agentfit_ai/recoverable_analysis.py",
    "ai_service/agentfit_ai/recoverable_draft_evaluation.py",
)
FORBIDDEN_ARTIFACT_KEYS = frozenset({"document", "raw", "response", "api_key", "profile"})


def options():
    return {"model": "solar-pro4", "prompt_revision": "v2",
            "candidate_occurrences": True, "keyed_candidates": True,
            "review_effort": "medium", "compact_review": True,
            "analysis_timeout_seconds": 60}


class CountingTransport:
    def __init__(self, provider):
        self.provider = provider
        self.calls = 0

    def __call__(self, payload, key, timeout):
        self.calls += 1
        return self.provider(payload, key, timeout)


def _structural_evidence_errors(document, case_id, profile):
    try:
        validate_profile(document, case_id, {
            "data": profile["data"],
            "evidence": {field: [{"start": span["start"], "end": span["end"]}
                         for span in profile["evidence"][field]] for field in FIELDS},
        })
    except (ProfileValidationError, KeyError, TypeError, ValueError):
        return 1
    return 0


def run_case(case, key, *, provider=post_solar,
             analyzer_factory=RecoverableAnchoredAnalyzer, clock=time.monotonic):
    transport = CountingTransport(provider)
    analyzer = analyzer_factory(key, transport=transport, **options())
    started = clock()
    result = analyzer.analyze_recoverable(case["document"], case["id"])
    elapsed_ms = round((clock() - started) * 1000)
    outcome = result["outcome"]
    row = {"id": case["id"], "kind": case["kind"], "outcome": outcome,
           "error": result.get("error"), "analysis_runs": 1,
           "provider_calls": transport.calls, "elapsed_ms": elapsed_ms,
           "questions": len(result.get("questions", [])),
           "unresolved_fields": sum(state == "unresolved" for state in
                                    result.get("fieldStates", {}).values()),
           "suggested_fields": 0, "unassessed_suggested_fields": 0,
           "semantic_evidence_unassessed": 0,
           "correct_suggestions": 0, "wrong_suggestions": 0,
           "false_confirmations": 0, "structural_evidence_errors": 0}
    if outcome == "failed":
        return row
    profile = result["profile"]
    row["structural_evidence_errors"] = _structural_evidence_errors(
        case["document"], case["id"], profile)
    if row["structural_evidence_errors"]:
        return row
    suggested = {field for field in FIELDS if profile["data"][field] is not None}
    row["suggested_fields"] = len(suggested)
    # Full references grade all field values, but do not provide independently
    # adjudicated evidence spans. Focus references only grade listed targets.
    row["semantic_evidence_unassessed"] = len(suggested)
    if case["kind"] == "full":
        score = full_score(profile, case["gold"])
        wrong = set(score["mismatch_fields"]) & suggested
        row["correct_suggestions"] = len(suggested - wrong)
        row["wrong_suggestions"] = len(wrong)
    else:
        row["unassessed_suggested_fields"] = len(suggested)
        score = focus_score(case, profile)
        row["correct_suggestions"] = score["matched"]
        row["wrong_suggestions"] = score["false_confirmations"]
    row["false_confirmations"] = score["false_confirmations"] if outcome == "complete" else 0
    row["matched"] = score["matched"]
    row["gold_total"] = score["total"]
    row["passed"] = score["passed"]
    return row


def aggregate(rows, *, planned=20):
    outcomes = Counter(row["outcome"] for row in rows)
    prior_failures = [row for row in rows if row["outcome"] != "complete"]
    elapsed = sorted(row["elapsed_ms"] for row in rows)
    def total(subset, key):
        return sum(row[key] for row in subset)
    def by_kind(subset, kind):
        return [row for row in subset if row["kind"] == kind]
    failure_types = {}
    for code in sorted({row.get("error") or "ANALYSIS_FAILURE" for row in prior_failures}):
        subset = [row for row in prior_failures if (row.get("error") or "ANALYSIS_FAILURE") == code]
        failure_types[code] = {
            "cases": len(subset),
            "needs_confirmation": sum(row["outcome"] == "needs_confirmation" for row in subset),
            "failed": sum(row["outcome"] == "failed" for row in subset),
            "suggested_fields": total(subset, "suggested_fields"),
            "full_correct_fields": total(by_kind(subset, "full"), "correct_suggestions"),
            "full_wrong_fields": total(by_kind(subset, "full"), "wrong_suggestions"),
            "focus_matched_targets": total(by_kind(subset, "focus"), "correct_suggestions"),
            "focus_forbidden_hits": total(by_kind(subset, "focus"), "wrong_suggestions"),
            "unassessed_suggested_fields": total(subset, "unassessed_suggested_fields"),
            "questions": total(subset, "questions"),
        }
    gate = {
        "all_cases_accounted": len(rows) == planned,
        "one_analysis_per_case": all(row["analysis_runs"] == 1 for row in rows),
        "six_call_limit": all(row["provider_calls"] <= 6 for row in rows),
        "observed_60s_limit": all(row["elapsed_ms"] <= 60000 for row in rows),
        "zero_wrong_auto_confirmations": all(
            row["false_confirmations"] == 0 for row in rows),
        "zero_structural_evidence_errors": all(
            row["structural_evidence_errors"] == 0 for row in rows),
        "all_suggestions_semantically_assessed": all(
            row["unassessed_suggested_fields"] == 0 for row in rows),
        "semantic_evidence_zero_errors_verified": all(
            row["semantic_evidence_unassessed"] == 0 for row in rows),
    }
    return {
        "planned_cases": planned, "evaluated_cases": len(rows),
        "complete_cases": outcomes["complete"],
        "needs_confirmation_cases": outcomes["needs_confirmation"],
        "failed_cases": outcomes["failed"],
        "prior_failure_cases": len(prior_failures),
        "suggested_fields_from_prior_failures": total(prior_failures, "suggested_fields"),
        "full_correct_fields_from_prior_failures": total(
            by_kind(prior_failures, "full"), "correct_suggestions"),
        "full_wrong_fields_from_prior_failures": total(
            by_kind(prior_failures, "full"), "wrong_suggestions"),
        "focus_matched_targets_from_prior_failures": total(
            by_kind(prior_failures, "focus"), "correct_suggestions"),
        "focus_forbidden_hits_from_prior_failures": total(
            by_kind(prior_failures, "focus"), "wrong_suggestions"),
        "unassessed_suggested_fields": total(rows, "unassessed_suggested_fields"),
        "semantic_evidence_unassessed": total(rows, "semantic_evidence_unassessed"),
        "questions": sum(row["questions"] for row in rows),
        "wrong_auto_confirmations": sum(row["false_confirmations"] for row in rows),
        "max_provider_calls": max((row["provider_calls"] for row in rows), default=0),
        "median_elapsed_ms": statistics.median(elapsed) if elapsed else None,
        "p95_elapsed_ms": elapsed[(95 * len(elapsed) + 99) // 100 - 1] if elapsed else None,
        "failure_types": failure_types,
        "gate": gate, "passed": bool(rows) and all(gate.values()),
        "scoring_note": "Full cases grade all field values; focus cases grade only listed target spans and forbidden strings. Focus suggestions outside that scope and semantic evidence in all cases remain unverified.",
    }


def write_json(path, value):
    def check(item):
        if type(item) is dict:
            if set(item) & FORBIDDEN_ARTIFACT_KEYS:
                raise ValueError("artifact contains forbidden key")
            for nested in item.values():
                check(nested)
        elif type(item) is list:
            for nested in item:
                check(nested)
    check(value)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def load_key(env_file):
    if env_file is None:
        raise ValueError("--env-file is required for live evaluation")
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("UPSTAGE_API_KEY="):
            key = line.partition("=")[2].strip().strip('"').strip("'")
            if key:
                return key
    raise ValueError("UPSTAGE_API_KEY missing")


def main():
    parser = argparse.ArgumentParser(description="Single-run recoverable draft evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, dataset_hashes = load_profile_cases()
    if len(cases) != 20:
        raise ValueError("expected 20 frozen synthetic cases")
    key = load_key(args.env_file)
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"model": "solar-pro4", "options": options(), "cases": len(cases),
            "dataset_sha256": dataset_hashes, "held_out": False,
            "one_analysis_per_case": True,
            "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in CODE_PATHS}}
    write_json(args.output / "plan.json", plan)
    rows = []
    for case in cases:
        row = run_case(case, key)
        rows.append(row)
        write_json(args.output / "results.json", rows)
        print(json.dumps({"id": row["id"], "outcome": row["outcome"],
                          "error": row["error"], "elapsed_ms": row["elapsed_ms"],
                          "provider_calls": row["provider_calls"]}), flush=True)
    summary = aggregate(rows)
    write_json(args.output / "summary.json", summary)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
