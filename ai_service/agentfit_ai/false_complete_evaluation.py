"""One-run opt-in evaluation of where false completions first diverge."""

import argparse
import hashlib
import json
import statistics
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .diagnostics import safe_code
from .false_complete_observation import ObservedRecoverableAnalyzer
from .false_complete_scoring import diagnose_case, load_gold_evidence
from .keyed_profile_evaluation import focus_score, full_score, load_profile_cases
from .recoverable_draft_evaluation import (
    CountingTransport, FORBIDDEN_ARTIFACT_KEYS, ROOT,
    _structural_evidence_errors, load_key, options,
)
from .solar import post_solar


CODE_PATHS = (
    "ai_service/agentfit_ai/anchored_analysis.py",
    "ai_service/agentfit_ai/recoverable_analysis.py",
    "ai_service/agentfit_ai/false_complete_observation.py",
    "ai_service/agentfit_ai/false_complete_scoring.py",
    "ai_service/agentfit_ai/false_complete_evaluation.py",
    "specs/ai-developer/04-analysis-provider/false-complete-diagnostics/gold-evidence.json",
)


@lru_cache(maxsize=1)
def _canonical_evidence():
    cases, _ = load_profile_cases()
    return load_gold_evidence(cases)


def run_case(case: dict, key: str, *, provider=post_solar,
             analyzer_factory=ObservedRecoverableAnalyzer,
             clock=time.monotonic) -> dict:
    transport = CountingTransport(provider)
    analyzer = analyzer_factory(key, transport=transport, **options())
    started = clock()
    result, observation = analyzer.analyze_observed(case["document"], case["id"])
    elapsed_ms = round((clock() - started) * 1000)
    outcome = result["outcome"]
    row = {"id": case["id"], "kind": case["kind"], "outcome": outcome,
           "error": safe_code(result.get("error")) if result.get("error") else None,
           "analysis_runs": 1, "provider_calls": transport.calls,
           "elapsed_ms": elapsed_ms, "false_confirmations": 0,
           "false_complete_fields": [], "diagnostic_error": None,
           "structural_evidence_errors": 0}
    if outcome == "failed":
        return row
    profile = result["profile"]
    row["structural_evidence_errors"] = _structural_evidence_errors(
        case["document"], case["id"], profile)
    if row["structural_evidence_errors"]:
        return row
    score = (full_score(profile, case["gold"]) if case["kind"] == "full"
             else focus_score(case, profile))
    row["false_confirmations"] = (score["false_confirmations"]
                                  if outcome == "complete" else 0)
    if row["false_confirmations"]:
        try:
            row["false_complete_fields"] = diagnose_case(
                case, result, observation, _canonical_evidence())
        except (KeyError, TypeError, ValueError, IndexError):
            row["diagnostic_error"] = "DIAGNOSTIC_UNDETERMINED"
            row["false_complete_fields"] = [{
                "field": None, "first_observed_divergence": "undetermined",
                "review_detected": None, "candidate_ids": [], "evidence_spans": [],
            }]
    return row


def aggregate(rows: list[dict], *, planned: int = 20) -> dict:
    outcomes = Counter(row["outcome"] for row in rows)
    stages = Counter(item["first_observed_divergence"] for row in rows
                     for item in row["false_complete_fields"])
    reviews = Counter(str(item["review_detected"]).lower() for row in rows
                      for item in row["false_complete_fields"])
    elapsed = sorted(row["elapsed_ms"] for row in rows)
    gate = {
        "all_cases_accounted": len(rows) == planned,
        "one_analysis_per_case": all(row["analysis_runs"] == 1 for row in rows),
        "six_call_limit": all(row["provider_calls"] <= 6 for row in rows),
        "observed_60s_limit": all(row["elapsed_ms"] <= 60000 for row in rows),
        "zero_wrong_auto_confirmations": all(
            row["false_confirmations"] == 0 for row in rows),
        "zero_structural_evidence_errors": all(
            row.get("structural_evidence_errors", 0) == 0 for row in rows),
    }
    return {"planned_cases": planned, "evaluated_cases": len(rows),
            "complete_cases": outcomes["complete"],
            "needs_confirmation_cases": outcomes["needs_confirmation"],
            "failed_cases": outcomes["failed"],
            "wrong_auto_confirmations": sum(row["false_confirmations"] for row in rows),
            "first_observed_divergence": dict(stages),
            "review_detected": dict(reviews),
            "undetermined": stages["undetermined"],
            "observed_over_60s": sum(row["elapsed_ms"] > 60000 for row in rows),
            "max_provider_calls": max((row["provider_calls"] for row in rows), default=0),
            "median_elapsed_ms": statistics.median(elapsed) if elapsed else None,
            "p95_elapsed_ms": elapsed[(95 * len(elapsed) + 99) // 100 - 1] if elapsed else None,
            "gate": gate, "passed": bool(rows) and all(gate.values()),
            "scoring_note": "Existing full/focus value scoring; semantic evidence remains unverified. Stage labels are observations, not causes."}


def write_safe_json(path: Path, value, *, forbidden_strings=()):
    def check(item):
        if type(item) is dict:
            if set(item) & FORBIDDEN_ARTIFACT_KEYS:
                raise ValueError("artifact contains forbidden key")
            for key, nested in item.items():
                check(key)
                check(nested)
        elif type(item) in (list, tuple):
            for nested in item:
                check(nested)
        elif type(item) is str and any(secret and secret in item
                                       for secret in forbidden_strings):
            raise ValueError("artifact contains source text")
    check(value)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="One-run false-complete stage diagnosis")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, dataset_hashes = load_profile_cases()
    if len(cases) != 20:
        raise ValueError("expected 20 frozen synthetic cases")
    _canonical_evidence()
    key = load_key(args.env_file)
    forbidden = [key, *(case["document"] for case in cases)]
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"model": "solar-pro4", "options": options(), "cases": len(cases),
            "dataset_sha256": dataset_hashes, "held_out": False,
            "one_analysis_per_case": True,
            "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in CODE_PATHS}}
    write_safe_json(args.output / "plan.json", plan, forbidden_strings=forbidden)
    rows = []
    for case in cases:
        row = run_case(case, key)
        rows.append(row)
        write_safe_json(args.output / "results.json", rows, forbidden_strings=forbidden)
        print(json.dumps({"id": row["id"], "outcome": row["outcome"],
                          "error": row["error"], "elapsed_ms": row["elapsed_ms"],
                          "provider_calls": row["provider_calls"],
                          "false_confirmations": row["false_confirmations"]}), flush=True)
    summary = aggregate(rows)
    write_safe_json(args.output / "summary.json", summary, forbidden_strings=forbidden)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
