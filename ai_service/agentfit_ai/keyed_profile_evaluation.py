"""Tuning-only paired whole-Profile evaluation; never persists source or model output."""

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from .anchored_analysis import AnchoredAnalyzer
from .anchored_evaluation import safe_diagnostics
from .embedding_section_evaluation import gold_spans, load_cases, load_key
from .repair_observation import score_profile
from .solar import AnalysisError


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = {
    "E01": ["Spring Boot", "MySQL", "별구름"],
    "E02": ["Vue", "Redis", "React"],
    "E03": ["Aurora", "가짜 결제"],
    "E04": ["Angular", "SMS", "시연용 메일"],
    "E05": ["FastAPI", "MCP 클라이언트"],
    "E06": ["Node", "해오름 3", "배송 추적"],
    "E07": ["MariaDB", "AWS", "MongoDB"],
    "E08": ["추천 AI", "개발용 로컬 파일"],
}
FIRST_GOLD = [
    {"features": [["장소 확인"], ["후보 선택"]]},
    {"features": [["회원 승인을 요청", "회원 승인을 요청한다", "사용자는 회원 승인을 요청한다", "사용자는 회원 승인을 요청한다."],
                  ["회원 승인을 처리", "회원 승인을 처리한다", "운영자는 회원 승인을 처리한다", "운영자는 회원 승인을 처리한다."]]},
    {}, {"external_integrations": []}, {}, {"features": [["일정 추천"]]},
]


def load_profile_cases():
    first = ROOT / "ai_service/tests/fixtures/quote-extraction-cases.json"
    second = ROOT / "specs/ai-developer/04-analysis-provider/anchored-prompt-contract/new-cases.json"
    cases = json.loads(first.read_text(encoding="utf-8"))
    cases = [dict(item, gold=gold, kind="full") for item, gold in zip(cases, FIRST_GOLD)]
    cases += [dict(item, kind="full") for item in json.loads(second.read_text(encoding="utf-8"))]
    focus, focus_hash = load_cases()
    cases += [dict(item, forbidden=FORBIDDEN[item["id"]], kind="focus") for item in focus]
    return cases, [hashlib.sha256(first.read_bytes()).hexdigest(),
                   hashlib.sha256(second.read_bytes()).hexdigest(), focus_hash]


def focus_score(case, profile):
    expected = gold_spans(case)
    matched = 0
    for item, (start, end) in zip(case["gold"], expected):
        field = item["field"]
        actual = profile["data"].get(field)
        values = actual if type(actual) is list else [actual] if type(actual) is str else []
        spans = profile["evidence"].get(field, [])
        if any(item["quote"] in value for value in values) and any(
                span["start"] <= start and span["end"] >= end for span in spans):
            matched += 1
    values = [item for value in profile["data"].values()
              for item in (value if type(value) is list else [value] if type(value) is str else [])]
    false_confirmations = sum(any(word in value for value in values) for word in case.get("forbidden", []))
    return {"matched": matched, "total": len(expected), "false_confirmations": false_confirmations,
            "passed": matched == len(expected) and false_confirmations == 0}


def full_score(profile, gold):
    score = score_profile(profile, gold)
    return {"passed": score["passed"], "matched": sum(
        item["matched"] for item in score["fields"].values()), "total": 10,
        "mismatch_fields": score["mismatch_fields"],
        "false_confirmations": sum(profile["data"][field] is not None
                                   for field in score["mismatch_fields"])}


def run_case(case, key, keyed):
    analyzer = AnchoredAnalyzer(key, model="solar-pro4", prompt_revision="v2",
                                candidate_occurrences=True, keyed_candidates=keyed,
                                review_effort="medium")
    try:
        result = analyzer.analyze(case["document"], case["id"])
        if case["kind"] == "full":
            score = full_score(result.profile, case["gold"])
        else:
            score = focus_score(case, result.profile)
        return {**score, "provider_calls": result.provider_calls, "elapsed_ms": result.elapsed_ms,
                "first_pass": result.first_pass_validated,
                **safe_diagnostics(result.diagnostics)}
    except AnalysisError as error:
        diagnostics = error.diagnostics or {}
        calls = diagnostics.get("calls", [])
        return {"error": error.code, "provider_calls": len(calls),
                "elapsed_ms": diagnostics.get("elapsed_ms", 0),
                **safe_diagnostics(diagnostics)}


def summarize(rows, arm):
    outcomes = [row[arm] for row in rows]
    valid = [item for item in outcomes if "error" not in item]
    elapsed = sorted(item.get("elapsed_ms", 0) for item in outcomes)
    errors = {}
    for item in outcomes:
        if "error" in item:
            errors[item["error"]] = errors.get(item["error"], 0) + 1
    return {"valid": len(valid), "passed": sum(item["passed"] for item in valid),
            "matched": sum(item["matched"] for item in valid),
            "total_valid": sum(item["total"] for item in valid),
            "total_planned": sum(row["gold_total"] for row in rows),
            "false_confirmations": sum(item["false_confirmations"] for item in valid),
            "errors": errors, "max_calls": max((item["provider_calls"] for item in outcomes), default=0),
            "median_ms": statistics.median(elapsed) if elapsed else 0,
            "p95_ms": elapsed[(95 * len(elapsed) + 99) // 100 - 1] if elapsed else 0}


def validation_error_count(summary):
    return sum(count for code, count in summary["errors"].items()
               if not code.startswith("PROVIDER_") and code not in
               ("ANALYSIS_DEADLINE", "CALL_LIMIT"))


def main():
    parser = argparse.ArgumentParser(description="Paired tuning-only whole Profile comparison")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, hashes = load_profile_cases()
    key = load_key("UPSTAGE_API_KEY")
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"model": "solar-pro4", "prompt_revision": "v2", "candidate_occurrences": True,
            "review_effort": "medium", "source_repair": False, "held_out": False,
            "cases": len(cases), "dataset_sha256": hashes,
            "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "analyzer_sha256": hashlib.sha256((ROOT / "ai_service/agentfit_ai/anchored_analysis.py").read_bytes()).hexdigest(),
            "order": "even=baseline,new; odd=new,baseline",
            "gate": "new false confirmations and validation errors do not exceed baseline; both <=6 calls and <=60s"}
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    rows = []
    for index, case in enumerate(cases):
        arms = ("baseline", "new") if index % 2 == 0 else ("new", "baseline")
        row = {"id": case["id"], "kind": case["kind"], "gold_total": 10 if case["kind"] == "full" else len(case["gold"]),
               "order": list(arms)}
        for arm in arms:
            row[arm] = run_case(case, key, arm == "new")
        rows.append(row)
        (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"], "baseline": row["baseline"].get("matched"),
                          "new": row["new"].get("matched"), "baseline_error": row["baseline"].get("error"),
                          "new_error": row["new"].get("error")}), flush=True)
    groups = {}
    for kind in ("full", "focus"):
        subset = [row for row in rows if row["kind"] == kind]
        paired = [row for row in subset if all("error" not in row[arm] for arm in ("baseline", "new"))]
        groups[kind] = {arm: summarize(subset, arm) for arm in ("baseline", "new")}
        groups[kind]["paired_cases"] = len(paired)
        groups[kind]["paired"] = {arm: summarize(paired, arm) for arm in ("baseline", "new")}
    budget_ok = all(item[arm]["provider_calls"] <= 6 and item[arm].get("elapsed_ms", 0) <= 60000
                    for item in rows for arm in ("baseline", "new"))
    baseline_errors = sum(sum(group["baseline"]["errors"].values()) for group in groups.values())
    new_errors = sum(sum(group["new"]["errors"].values()) for group in groups.values())
    baseline_false = sum(group["baseline"]["false_confirmations"] for group in groups.values())
    new_false = sum(group["new"]["false_confirmations"] for group in groups.values())
    baseline_validation = sum(validation_error_count(group["baseline"]) for group in groups.values())
    new_validation = sum(validation_error_count(group["new"]) for group in groups.values())
    gate = {"same_cases": len(rows) == 20, "budget": budget_ok,
            "false_confirmations_no_increase": new_false <= baseline_false,
            "validation_errors_no_increase": new_validation <= baseline_validation,
            "errors_no_increase": new_errors <= baseline_errors}
    (args.output / "summary.json").write_text(json.dumps(
        {"groups": groups, "gate": gate, "passed": all(gate.values())},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(gate.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
