"""Synthetic-only paired Solar/DeepSeek semantic review comparison."""

import argparse
import hashlib
import json
from pathlib import Path

from .analysis_timeout_evaluation import ReviewCappedAnchoredAnalyzer
from .anchored_evaluation import safe_diagnostics
from .compact_review_evaluation import aggregate
from .deepseek_evaluation import MODEL as DEEPSEEK_MODEL, load_key as load_nvidia_key
from .embedding_section_evaluation import load_key as load_solar_key
from .keyed_profile_evaluation import focus_score, full_score, load_profile_cases
from .solar import AnalysisError


ROOT = Path(__file__).resolve().parents[2]
ARMS = ("baseline", "compact")
SAFE_MODELS = {"solar-pro4", "solar-pro4-260806", DEEPSEEK_MODEL}


def safe_model_diagnostics(diagnostic):
    safe = safe_diagnostics(diagnostic)
    for source, target in zip(diagnostic.get("calls", []), safe["calls"]):
        if source.get("model") in SAFE_MODELS:
            target["model"] = source["model"]
    return safe


def run_case(case, solar_key, nvidia_key, routed):
    options = {"review_model": DEEPSEEK_MODEL, "review_api_key": nvidia_key} if routed else {}
    analyzer = ReviewCappedAnchoredAnalyzer(
        solar_key, model="solar-pro4", prompt_revision="v2", candidate_occurrences=True,
        keyed_candidates=True, review_effort="medium", compact_review=True,
        analysis_timeout_seconds=60, **options)
    try:
        result = analyzer.analyze(case["document"], case["id"])
        score = (full_score(result.profile, case["gold"]) if case["kind"] == "full"
                 else focus_score(case, result.profile))
        return {**score, "provider_calls": result.provider_calls,
                "elapsed_ms": result.elapsed_ms, "first_pass": result.first_pass_validated,
                **safe_model_diagnostics(result.diagnostics)}
    except AnalysisError as error:
        diagnostic = error.diagnostics or {}
        return {"error": error.code, "provider_calls": len(diagnostic.get("calls", [])),
                "elapsed_ms": diagnostic.get("elapsed_ms", 0),
                **safe_model_diagnostics(diagnostic)}


def main():
    parser = argparse.ArgumentParser(description="Paired Solar/DeepSeek compact review evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, dataset_hashes = load_profile_cases()
    solar_key = load_solar_key("UPSTAGE_API_KEY")
    nvidia_key = load_nvidia_key()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = ("ai_service/agentfit_ai/anchored_analysis.py",
             "ai_service/agentfit_ai/solar.py",
             "ai_service/agentfit_ai/deepseek_evaluation.py",
             "ai_service/agentfit_ai/compact_review.py")
    plan = {
        "cases": len(cases), "dataset_sha256": dataset_hashes,
        "arm_labels": {"baseline": "Solar Pro4 review", "compact": "DeepSeek V4.1 Flash review"},
        "extraction_model": "solar-pro4", "review_model": DEEPSEEK_MODEL,
        "review_contract": "compact-review-v1", "prompt_revision": "v2",
        "review_effort": "medium on Solar; thinking=false on DeepSeek",
        "overall_timeout_seconds": 60, "per_call_cap_seconds": 40,
        "order": "even=baseline,compact; odd=compact,baseline", "held_out": False,
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                        for path in paths},
    }
    (args.output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for index, case in enumerate(cases):
        arms = ARMS if index % 2 == 0 else ARMS[::-1]
        row = {"id": case["id"], "kind": case["kind"],
               "gold_total": 10 if case["kind"] == "full" else len(case["gold"]),
               "order": list(arms)}
        for arm in arms:
            row[arm] = run_case(case, solar_key, nvidia_key, arm == "compact")
        rows.append(row)
        (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"], "baseline": row["baseline"].get("matched"),
                          "deepseek": row["compact"].get("matched"),
                          "baseline_error": row["baseline"].get("error"),
                          "deepseek_error": row["compact"].get("error")}), flush=True)
    summary = aggregate(rows)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
