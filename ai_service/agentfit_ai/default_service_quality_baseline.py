"""One-pass synthetic quality baseline for the production Worker's Solar settings."""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from .keyed_profile_evaluation import focus_score, full_score, load_profile_cases
from .recoverable_draft_evaluation import CountingTransport, ROOT, load_key
from .diagnostics import safe_code
from .solar import AnalysisError, SolarAnalyzer, post_solar_inline


CODE_PATHS = (
    "ai_service/agentfit_ai/analysis_worker.py",
    "ai_service/agentfit_ai/solar.py",
    "ai_service/agentfit_ai/semantic_review.py",
    "ai_service/agentfit_ai/default_service_quality_baseline.py",
)
FORBIDDEN_KEYS = frozenset({"document", "raw", "response", "api_key", "profile", "gold"})


def run_case(case, key, *, analyzer_factory=SolarAnalyzer, provider=post_solar_inline,
             clock=time.monotonic):
    transport = CountingTransport(provider)
    analyzer = analyzer_factory(
        key, transport=transport, model="solar-pro4", evidence_contract=True,
        semantic_review=True, analysis_timeout_seconds=40)
    start = clock()
    try:
        result = analyzer.analyze(case["document"], case["id"])
    except AnalysisError as error:
        return {"id": case["id"], "kind": case["kind"], "outcome": "failed",
                "error": safe_code(error.code), "provider_calls": transport.calls or getattr(error, "provider_calls", 0),
                "elapsed_ms": round((clock() - start) * 1000),
                "matched": None, "gold_total": 10 if case["kind"] == "full" else len(case["gold"]),
                "false_confirmations": None, "mismatch_fields": [], "passed": False}
    score = (full_score(result.profile, case["gold"]) if case["kind"] == "full"
             else focus_score(case, result.profile))
    return {"id": case["id"], "kind": case["kind"], "outcome": "complete",
            "error": None, "provider_calls": transport.calls or result.provider_calls,
            "elapsed_ms": round((clock() - start) * 1000),
            "matched": score["matched"], "gold_total": score["total"],
            "false_confirmations": score["false_confirmations"],
            "mismatch_fields": score.get("mismatch_fields", []), "passed": score["passed"]}


def aggregate(rows, *, planned=20):
    outcomes = Counter(row["outcome"] for row in rows)
    completed = [row for row in rows if row["outcome"] == "complete"]
    gate = {
        "all_cases_accounted": len(rows) == planned,
        "zero_failed_cases": outcomes["failed"] == 0,
        "all_complete_cases_correct": all(row["passed"] for row in completed),
        "zero_wrong_auto_confirmations": all(row["false_confirmations"] == 0 for row in completed),
        "six_call_limit": all(row["provider_calls"] <= 6 for row in rows),
        "observed_60s_limit": all(row["elapsed_ms"] <= 60000 for row in rows),
    }
    return {"planned_cases": planned, "evaluated_cases": len(rows),
            "complete_cases": outcomes["complete"], "failed_cases": outcomes["failed"],
            "passed_cases": sum(row["passed"] for row in completed),
            "matched": sum(row["matched"] for row in completed),
            "gold_total_completed": sum(row["gold_total"] for row in completed),
            "gold_total_planned": sum(row["gold_total"] for row in rows),
            "wrong_auto_confirmations": sum(row["false_confirmations"] for row in completed),
            "max_provider_calls": max((row["provider_calls"] for row in rows), default=0),
            "max_elapsed_ms": max((row["elapsed_ms"] for row in rows), default=0),
            "errors": dict(Counter(row["error"] for row in rows if row["error"])),
            "gate": gate, "passed": bool(rows) and all(gate.values()),
            "limitation": "Synthetic reused cases; mirrors Worker analyzer settings, not the subprocess or HTTP path. Full-case non-null mismatches are counted as false confirmations; semantic evidence is not independently adjudicated. This does not establish production readiness."}


def write_report(output, plan, rows, summary, *, forbidden=()):
    def inspect(value):
        if type(value) is dict:
            if set(value) & FORBIDDEN_KEYS:
                raise ValueError("forbidden report key")
            for key, item in value.items():
                inspect(key)
                inspect(item)
        elif type(value) is list:
            for item in value:
                inspect(item)
        elif type(value) is str and any(secret and secret in value for secret in forbidden):
            raise ValueError("forbidden report text")
    for value in (plan, rows, summary):
        inspect(value)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("plan", plan), ("results", rows), ("summary", summary)):
        (output / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Default Worker analyzer quality baseline")
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
    plan = {"model": "solar-pro4", "analysis_timeout_seconds": 40,
            "semantic_review": True, "evidence_contract": True,
            "cases": len(cases), "selected_case_ids": [case["id"] for case in cases],
            "dataset_sha256": hashes, "held_out": False,
            "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                            for name in CODE_PATHS}}
    forbidden = (key, *(case["document"] for case in cases))
    rows = []
    # Write before calls so an interrupted run still leaves an honest partial record.
    write_report(args.output, plan, rows, aggregate(rows, planned=len(cases)), forbidden=forbidden)
    for case in cases:
        row = run_case(case, key)
        rows.append(row)
        for name, value in (("results", rows), ("summary", aggregate(rows, planned=len(cases)))):
            (args.output / f"{name}.json").write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"], "outcome": row["outcome"],
                          "error": row["error"], "passed": row["passed"],
                          "false_confirmations": row["false_confirmations"],
                          "elapsed_ms": row["elapsed_ms"]}), flush=True)
    return 0 if aggregate(rows, planned=len(cases))["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
