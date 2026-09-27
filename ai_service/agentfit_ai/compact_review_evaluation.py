"""Tuning-only paired baseline/compact semantic review comparison."""

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from .analysis_timeout_evaluation import ReviewCappedAnchoredAnalyzer
from .anchored_evaluation import safe_diagnostics
from .embedding_section_evaluation import load_key
from .keyed_profile_evaluation import (
    focus_score, full_score, load_profile_cases, summarize, validation_error_count,
)
from .solar import AnalysisError


ROOT = Path(__file__).resolve().parents[2]
ARMS = ("baseline", "compact")


def run_case(case, key, compact):
    analyzer = ReviewCappedAnchoredAnalyzer(
        key, model="solar-pro4", prompt_revision="v2", candidate_occurrences=True,
        keyed_candidates=True, review_effort="medium", compact_review=compact,
        analysis_timeout_seconds=60)
    try:
        result = analyzer.analyze(case["document"], case["id"])
        score = full_score(result.profile, case["gold"]) if case["kind"] == "full" else focus_score(case, result.profile)
        return {**score, "provider_calls": result.provider_calls,
                "elapsed_ms": result.elapsed_ms, "first_pass": result.first_pass_validated,
                **safe_diagnostics(result.diagnostics)}
    except AnalysisError as error:
        diagnostic = error.diagnostics or {}
        return {"error": error.code, "provider_calls": len(diagnostic.get("calls", [])),
                "elapsed_ms": diagnostic.get("elapsed_ms", 0),
                **safe_diagnostics(diagnostic)}


def review_metrics(rows, arm):
    timeouts = Counter()
    reasons = Counter()
    elapsed = []
    bytes_in = []
    tokens_out = []
    for row in rows:
        for call in row[arm].get("calls", []):
            if call.get("stage") not in ("semantic_review", "semantic_recheck"):
                continue
            if call.get("error") == "PROVIDER_TIMEOUT":
                timeouts[call["stage"]] += 1
            if call.get("error") == "SEMANTIC_REVIEW_INVALID" and call.get("review_error"):
                reasons[call["review_error"]["reason"]] += 1
            for target, key in ((elapsed, "provider_elapsed_ms"),
                                (bytes_in, "request_bytes"),
                                (tokens_out, "completion_tokens")):
                value = call.get(key)
                if type(value) is int:
                    target.append(value)
    return {"timeouts": dict(timeouts), "invalid_reasons": dict(reasons),
            "median_provider_ms": statistics.median(elapsed) if elapsed else None,
            "median_request_bytes": statistics.median(bytes_in) if bytes_in else None,
            "median_completion_tokens": statistics.median(tokens_out) if tokens_out else None}


def aggregate(rows):
    groups = {}
    for kind in ("full", "focus"):
        subset = [row for row in rows if row["kind"] == kind]
        paired = [row for row in subset if all("error" not in row[arm] for arm in ARMS)]
        groups[kind] = {arm: summarize(subset, arm) for arm in ARMS}
        groups[kind]["paired_cases"] = len(paired)
        groups[kind]["paired"] = {arm: summarize(paired, arm) for arm in ARMS}
    reviews = {arm: review_metrics(rows, arm) for arm in ARMS}
    outcomes = {arm: [row[arm] for row in rows] for arm in ARMS}
    total = lambda arm, key: sum(item.get(key, 0) for item in outcomes[arm])
    validation = lambda arm: sum(validation_error_count(groups[kind][arm]) for kind in ("full", "focus"))
    timeouts = lambda arm: sum(reviews[arm]["timeouts"].values())
    invalid = lambda arm: sum(reviews[arm]["invalid_reasons"].values())
    gate = {
        "same_cases": len(rows) == 20,
        "full_accuracy_no_regression": groups["full"]["compact"]["matched"] >= groups["full"]["baseline"]["matched"],
        "full_complete_no_regression": groups["full"]["compact"]["passed"] >= groups["full"]["baseline"]["passed"],
        "focus_accuracy_no_regression": groups["focus"]["compact"]["matched"] >= groups["focus"]["baseline"]["matched"],
        "false_confirmations_no_increase": total("compact", "false_confirmations") <= total("baseline", "false_confirmations"),
        "validation_errors_no_increase": validation("compact") <= validation("baseline"),
        "review_timeouts_decrease": timeouts("compact") < timeouts("baseline"),
        "review_invalid_decrease": invalid("compact") < invalid("baseline"),
        "total_successes_increase": total("compact", "passed") > total("baseline", "passed"),
        "six_call_limit": all(item["provider_calls"] <= 6 for arm in ARMS for item in outcomes[arm]),
        "observed_60s_limit": all(item.get("elapsed_ms", 0) <= 60000 for arm in ARMS for item in outcomes[arm]),
    }
    return {"groups": groups, "review": reviews, "gate": gate,
            "passed": all(gate.values()),
            "total_passed": {arm: total(arm, "passed") for arm in ARMS},
            "total_false_confirmations": {arm: total(arm, "false_confirmations") for arm in ARMS},
            "total_validation_errors": {arm: validation(arm) for arm in ARMS}}


def main():
    parser = argparse.ArgumentParser(description="Paired opt-in compact semantic review evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, dataset_hashes = load_profile_cases()
    key = load_key("UPSTAGE_API_KEY")
    args.output.mkdir(parents=True, exist_ok=False)
    paths = ["ai_service/agentfit_ai/anchored_analysis.py",
             "ai_service/agentfit_ai/compact_review.py",
             "ai_service/agentfit_ai/semantic_review.py"]
    plan = {
        "cases": len(cases), "dataset_sha256": dataset_hashes,
        "model": "solar-pro4", "candidate_contract": "keyed-v1",
        "prompt_revision": "v2", "review_effort": "medium",
        "overall_timeout_seconds": 60, "per_call_cap_seconds": 40,
        "order": "even=baseline,compact; odd=compact,baseline", "held_out": False,
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
        "gate": "no full/focus accuracy, false-confirmation or validation regression; fewer review timeouts and invalid replies; more final successes; <=6 calls and observed <=60s",
    }
    (args.output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for index, case in enumerate(cases):
        arms = ARMS if index % 2 == 0 else ARMS[::-1]
        row = {"id": case["id"], "kind": case["kind"],
               "gold_total": 10 if case["kind"] == "full" else len(case["gold"]),
               "order": list(arms)}
        for arm in arms:
            row[arm] = run_case(case, key, arm == "compact")
        rows.append(row)
        (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"],
                          "baseline": row["baseline"].get("matched"),
                          "compact": row["compact"].get("matched"),
                          "baseline_error": row["baseline"].get("error"),
                          "compact_error": row["compact"].get("error")}), flush=True)
    summary = aggregate(rows)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
