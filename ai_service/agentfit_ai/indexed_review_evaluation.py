"""Opt-in paired evaluation of explicit array item indexes in Solar review input."""

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from .default_service_quality_baseline import aggregate, run_case
from .false_complete_evaluation import write_safe_json
from .keyed_profile_evaluation import load_profile_cases
from .recoverable_draft_evaluation import ROOT, load_key
from .solar import SolarAnalyzer


CODE_PATHS = (
    "ai_service/agentfit_ai/analysis_worker.py",
    "ai_service/agentfit_ai/solar.py",
    "ai_service/agentfit_ai/semantic_review.py",
    "ai_service/agentfit_ai/default_service_quality_baseline.py",
    "ai_service/agentfit_ai/indexed_review_evaluation.py",
)


class IndexedReviewSolarAnalyzer(SolarAnalyzer):
    def _request_review(self, *args, **kwargs):
        kwargs["indexed_draft"] = True
        return super()._request_review(*args, **kwargs)


def run_arm(case, key, arm):
    analyzer = SolarAnalyzer if arm == "baseline" else IndexedReviewSolarAnalyzer
    return run_case(case, key, analyzer_factory=analyzer)


def run_pair(case, key, index, *, run_arm=run_arm):
    order = ("baseline", "indexed") if index % 2 == 0 else ("indexed", "baseline")
    row = {"id": case["id"], "kind": case["kind"], "order": list(order)}
    for arm in order:
        row[arm] = run_arm(case, key, arm)
    return row


def summarize(rows):
    arms = {arm: aggregate([row[arm] for row in rows], planned=len(rows))
            for arm in ("baseline", "indexed")}
    paired = [row for row in rows if all(row[arm]["outcome"] == "complete"
                                       for arm in ("baseline", "indexed"))]
    matched = {arm: sum(row[arm]["matched"] for row in paired)
               for arm in ("baseline", "indexed")}
    median = {arm: statistics.median(row[arm]["elapsed_ms"] for row in rows)
              if rows else None for arm in ("baseline", "indexed")}
    def array_errors(arm):
        return arms[arm]["review_invalid_reasons"].get("ARRAY_INDEX", 0)
    gate = {
        "all_pairs_accounted": bool(rows) and all(
            set(row) == {"id", "kind", "order", "baseline", "indexed"} for row in rows),
        "false_confirmations_no_increase": arms["indexed"]["wrong_auto_confirmations"] <=
                                           arms["baseline"]["wrong_auto_confirmations"],
        "failures_no_increase": arms["indexed"]["failed_cases"] <= arms["baseline"]["failed_cases"],
        "total_failures_decrease": arms["indexed"]["failed_cases"] < arms["baseline"]["failed_cases"],
        "correct_completions_no_decrease": arms["indexed"]["passed_cases"] >= arms["baseline"]["passed_cases"],
        "paired_accuracy_no_decrease": bool(paired) and matched["indexed"] >= matched["baseline"],
        "array_index_errors_no_increase": array_errors("indexed") <= array_errors("baseline"),
        "latency_no_increase": bool(rows) and median["indexed"] <= median["baseline"],
        "observable_improvement": (array_errors("indexed") < array_errors("baseline")
                                   or arms["indexed"]["passed_cases"] > arms["baseline"]["passed_cases"]),
    }
    return {"evaluated_pairs": len(rows), "paired_complete_cases": len(paired),
            "paired_matched": matched, "median_elapsed_ms": median,
            "arms": arms, "screen_gate": gate, "screen_passed": all(gate.values()),
            "limitation": "Reused synthetic cases and independent stochastic extraction in each arm; alternating order does not establish causality or production readiness."}


def main():
    parser = argparse.ArgumentParser(description="Paired indexed Solar review input evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--case-id", action="append")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, hashes = load_profile_cases()
    if len(cases) != 20:
        raise ValueError("expected 20 frozen cases")
    if args.case_id:
        selected = set(args.case_id)
        if len(selected) != len(args.case_id) or not selected <= {case["id"] for case in cases}:
            parser.error("invalid case selection")
        cases = [case for case in cases if case["id"] in selected]
    key = load_key(args.env_file)
    if args.output.exists():
        parser.error("output already exists")
    forbidden = (key, *(case["document"] for case in cases))
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"model": "solar-pro4", "review_effort": "medium",
            "analysis_timeout_seconds": 40, "arms": ["baseline", "indexed"],
            "order": "even baseline first, odd indexed first",
            "selected_case_ids": [case["id"] for case in cases], "held_out": False,
            "dataset_sha256": hashes,
            "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in CODE_PATHS}}
    write_safe_json(args.output / "plan.json", plan, forbidden_strings=forbidden)
    rows = []
    write_safe_json(args.output / "results.json", rows, forbidden_strings=forbidden)
    for index, case in enumerate(cases):
        row = run_pair(case, key, index)
        rows.append(row)
        write_safe_json(args.output / "results.json", rows, forbidden_strings=forbidden)
        write_safe_json(args.output / "summary.json", summarize(rows), forbidden_strings=forbidden)
        print(json.dumps({"id": row["id"],
                          "baseline": row["baseline"]["outcome"],
                          "indexed": row["indexed"]["outcome"],
                          "baseline_ms": row["baseline"]["elapsed_ms"],
                          "indexed_ms": row["indexed"]["elapsed_ms"]}), flush=True)
    return 0 if summarize(rows)["screen_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
