"""Opt-in paired comparison of default Solar semantic review effort."""

import argparse
import hashlib
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
    "ai_service/agentfit_ai/default_review_effort_comparison.py",
)


class ReviewEffortSolarAnalyzer(SolarAnalyzer):
    def __init__(self, *args, review_effort="medium", **kwargs):
        if review_effort not in ("medium", "low"):
            raise ValueError("unsupported review effort")
        super().__init__(*args, **kwargs)
        self._review_effort = review_effort

    def _request_review(self, *args, **kwargs):
        kwargs["reasoning_effort"] = self._review_effort
        return super()._request_review(*args, **kwargs)


def run_arm(case, key, effort):
    def analyzer_factory(api_key, **kwargs):
        return ReviewEffortSolarAnalyzer(api_key, review_effort=effort, **kwargs)
    return run_case(case, key, analyzer_factory=analyzer_factory)


def run_pair(case, key, index, *, run_arm=run_arm):
    order = ("medium", "low") if index % 2 == 0 else ("low", "medium")
    row = {"id": case["id"], "kind": case["kind"], "order": list(order)}
    for effort in order:
        row[effort] = run_arm(case, key, effort)
    return row


def summarize(rows):
    arms = {effort: aggregate([row[effort] for row in rows], planned=len(rows))
            for effort in ("medium", "low")}
    paired = [row for row in rows if all(row[effort]["outcome"] == "complete"
                                       for effort in ("medium", "low"))]
    elapsed = {effort: statistics.median(row[effort]["elapsed_ms"] for row in rows)
               if rows else None for effort in ("medium", "low")}
    paired_matched = {effort: sum(row[effort]["matched"] for row in paired)
                      for effort in ("medium", "low")}
    screen_gate = {
        "all_pairs_accounted": bool(rows) and all(set(row) == {"id", "kind", "order", "medium", "low"}
                                                for row in rows),
        "no_more_false_confirmations": arms["low"]["wrong_auto_confirmations"] <=
                                        arms["medium"]["wrong_auto_confirmations"],
        "no_more_failures": arms["low"]["failed_cases"] <= arms["medium"]["failed_cases"],
        "no_fewer_correct_completions": arms["low"]["passed_cases"] >= arms["medium"]["passed_cases"],
        "paired_recall_not_worse": bool(paired) and paired_matched["low"] >= paired_matched["medium"],
        "lower_median_latency": bool(rows) and elapsed["low"] < elapsed["medium"],
    }
    return {"evaluated_pairs": len(rows), "paired_complete_cases": len(paired),
            "paired_matched": paired_matched, "median_elapsed_ms": elapsed,
            "arms": arms, "screen_gate": screen_gate,
            "screen_passed": all(screen_gate.values()),
            "limitation": "Each arm uses one stochastic provider response per reused synthetic case; alternating order does not prove causality or production readiness. Never auto-promote low effort from this screen alone."}


def main():
    parser = argparse.ArgumentParser(description="Paired default review effort comparison")
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
    plan = {"model": "solar-pro4", "review_efforts": ["medium", "low"],
            "analysis_timeout_seconds": 40, "order": "even medium first, odd low first",
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
        print({"id": row["id"], "medium": row["medium"]["outcome"],
               "low": row["low"]["outcome"],
               "medium_ms": row["medium"]["elapsed_ms"],
               "low_ms": row["low"]["elapsed_ms"]}, flush=True)
    return 0 if summarize(rows)["screen_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
