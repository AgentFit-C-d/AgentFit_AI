"""Tuning-only paired 60/120-second comparison with a common 40-second call cap."""

import argparse
import hashlib
import json
from pathlib import Path

from .anchored_analysis import AnchoredAnalyzer
from .anchored_evaluation import safe_diagnostics
from .embedding_section_evaluation import load_key
from .keyed_profile_evaluation import (
    focus_score, full_score, load_profile_cases, summarize, validation_error_count,
)
from .solar import AnalysisError


ROOT = Path(__file__).resolve().parents[2]


class ReviewCappedAnchoredAnalyzer(AnchoredAnalyzer):
    """Evaluation-only cap; both duration arms use the same provider call limit."""

    def _request_review_uncapped(self, document, profile, *, _trace=None, timeout=40):
        return super()._request_review(document, profile, _trace=_trace, timeout=timeout)

    def _request_review(self, document, profile, *, _trace=None, timeout=40):
        return self._request_review_uncapped(document, profile, _trace=_trace,
                                             timeout=min(40, timeout))


def failure_stage(diagnostics, code):
    for call in reversed(diagnostics.get("calls", [])):
        if call.get("error") == code:
            return call.get("stage")
    if code in ("ANALYSIS_DEADLINE", "CALL_LIMIT"):
        return "between_calls"
    for call in reversed(diagnostics.get("calls", [])):
        if call.get("outcome") in ("failed", "validation_failed", "semantic_failed"):
            return call.get("stage")
    return None


def run_case(case, key, seconds):
    analyzer = ReviewCappedAnchoredAnalyzer(
        key, model="solar-pro4", prompt_revision="v2", candidate_occurrences=True,
        keyed_candidates=True, review_effort="medium",
        analysis_timeout_seconds=seconds)
    try:
        result = analyzer.analyze(case["document"], case["id"])
        score = full_score(result.profile, case["gold"]) if case["kind"] == "full" else focus_score(case, result.profile)
        return {**score, "provider_calls": result.provider_calls,
                "elapsed_ms": result.elapsed_ms, "first_pass": result.first_pass_validated,
                **safe_diagnostics(result.diagnostics)}
    except AnalysisError as error:
        diagnostic = error.diagnostics or {}
        return {"error": error.code, "error_stage": failure_stage(diagnostic, error.code),
                "provider_calls": len(diagnostic.get("calls", [])),
                "elapsed_ms": diagnostic.get("elapsed_ms", 0),
                **safe_diagnostics(diagnostic)}


def group_summary(rows):
    groups = {}
    for kind in ("full", "focus"):
        subset = [row for row in rows if row["kind"] == kind]
        paired = [row for row in subset if all("error" not in row[arm] for arm in ("sixty", "one_twenty"))]
        groups[kind] = {arm: summarize(subset, arm) for arm in ("sixty", "one_twenty")}
        groups[kind]["paired_cases"] = len(paired)
        groups[kind]["paired"] = {arm: summarize(paired, arm) for arm in ("sixty", "one_twenty")}
        groups[kind]["timeout_stages"] = {arm: {
            code: {stage: sum(row[arm].get("error") == code and row[arm].get("error_stage") == stage
                              for row in subset)
                   for stage in ("candidate_generation", "judgment", "semantic_review", "semantic_repair",
                                 "source_repair", "semantic_recheck", "between_calls", None)}
            for code in ("PROVIDER_TIMEOUT", "ANALYSIS_DEADLINE")}
            for arm in ("sixty", "one_twenty")}
    return groups


def aggregate(rows):
    groups = group_summary(rows)
    sixty = [row["sixty"] for row in rows]
    longer = [row["one_twenty"] for row in rows]
    passed = lambda outcomes: sum(item.get("passed", False) for item in outcomes)
    false = lambda outcomes: sum(item.get("false_confirmations", 0) for item in outcomes)
    validation = lambda arm: sum(validation_error_count(groups[kind][arm]) for kind in ("full", "focus"))
    gate = {
        "same_cases": len(rows) == 20,
        "successes_increase": passed(longer) > passed(sixty),
        "full_accuracy_no_regression": groups["full"]["one_twenty"]["matched"] >= groups["full"]["sixty"]["matched"],
        "focus_accuracy_no_regression": groups["focus"]["one_twenty"]["matched"] >= groups["focus"]["sixty"]["matched"],
        "false_confirmations_no_increase": false(longer) <= false(sixty),
        "validation_errors_no_increase": validation("one_twenty") <= validation("sixty"),
        "six_call_limit": all(item["provider_calls"] <= 6 for item in sixty + longer),
        "observed_60s_limit": all(item.get("elapsed_ms", 0) <= 60000 for item in sixty),
        "observed_120s_limit": all(item.get("elapsed_ms", 0) <= 120000 for item in longer),
    }
    return {"groups": groups, "gate": gate, "passed": all(gate.values()),
            "total_passed": {"sixty": passed(sixty), "one_twenty": passed(longer)},
            "total_false_confirmations": {"sixty": false(sixty), "one_twenty": false(longer)},
            "total_validation_errors": {"sixty": validation("sixty"), "one_twenty": validation("one_twenty")}}


def main():
    parser = argparse.ArgumentParser(description="Paired overall timeout experiment")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--reaggregate", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.live == args.reaggregate:
        parser.error("select exactly one of --live or --reaggregate")
    if args.reaggregate:
        rows = json.loads((args.output / "results.json").read_text(encoding="utf-8"))
        for row in rows:
            for arm in ("sixty", "one_twenty"):
                item = row[arm]
                if "error" in item:
                    item["error_stage"] = failure_stage(item, item["error"])
        (args.output / "results-reviewed.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = aggregate(rows)
        summary["aggregation_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (args.output / "summary-reviewed.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0 if summary["passed"] else 1
    cases, dataset_hashes = load_profile_cases()
    key = load_key("UPSTAGE_API_KEY")
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {
        "cases": len(cases), "dataset_sha256": dataset_hashes, "model": "solar-pro4",
        "candidate_contract": "keyed-v1", "prompt_revision": "v2", "review_effort": "medium",
        "per_call_cap_seconds": 40, "durations_seconds": [60, 120],
        "order": "even=60,120; odd=120,60", "held_out": False,
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "solar_sha256": hashlib.sha256((ROOT / "ai_service/agentfit_ai/solar.py").read_bytes()).hexdigest(),
        "anchored_sha256": hashlib.sha256((ROOT / "ai_service/agentfit_ai/anchored_analysis.py").read_bytes()).hexdigest(),
        "gate": "120s successes increase; full and focus matched scores do not regress; false confirmations and validation errors do not increase; <=6 calls; observed <=60s and <=120s",
    }
    (args.output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for index, case in enumerate(cases):
        arms = ("sixty", "one_twenty") if index % 2 == 0 else ("one_twenty", "sixty")
        row = {"id": case["id"], "kind": case["kind"],
               "gold_total": 10 if case["kind"] == "full" else len(case["gold"]),
               "order": list(arms)}
        for arm in arms:
            row[arm] = run_case(case, key, 60 if arm == "sixty" else 120)
        rows.append(row)
        (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"],
                          "sixty": row["sixty"].get("matched"),
                          "one_twenty": row["one_twenty"].get("matched"),
                          "sixty_error": row["sixty"].get("error"),
                          "one_twenty_error": row["one_twenty"].get("error")}), flush=True)
    summary = aggregate(rows)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
