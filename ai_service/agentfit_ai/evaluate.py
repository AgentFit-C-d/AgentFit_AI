"""Explicitly opted-in, synthetic-only Solar evaluation."""
import argparse
import json
import os
import time
from pathlib import Path

from .evidence import CONTRACT_VERSION
from .solar import AnalysisError, SolarAnalyzer, PROMPT_VERSION, REASONING_EFFORT, FREQUENCY_PENALTY
from .semantic_review import REVIEW_PROMPT, REVIEW_REASONING_EFFORT, REVIEW_MAX_TOKENS
from .profile import FIELDS

ROOT = Path(__file__).resolve().parents[2]
CASES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "solar-cases.json"


def load_api_key():
    value = os.environ.get("UPSTAGE_API_KEY", "").strip()
    if value:
        return value
    try:
        lines = (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        raise AnalysisError("MISSING_OR_INVALID_KEY") from None
    matches = [line.partition("=")[2].strip() for line in lines if line.startswith("UPSTAGE_API_KEY=")]
    if len(matches) != 1:
        raise AnalysisError("MISSING_OR_INVALID_KEY")
    value = matches[0]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def main():
    parser = argparse.ArgumentParser(description="Evaluate fixed synthetic cases; never prints model content.")
    parser.add_argument("--live", action="store_true", help="Allow billable Upstage requests")
    parser.add_argument("--report", type=Path, help="Write aggregate metadata and case outcomes only")
    parser.add_argument("--diagnostics-dir", type=Path, help="Opt-in local diagnostics; failed raw responses expire after 7 days")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required to call Upstage")
    try:
        from .diagnostics import LocalDiagnosticsStore
        store = LocalDiagnosticsStore(args.diagnostics_dir) if args.diagnostics_dir else None
        analyzer = SolarAnalyzer(load_api_key(), diagnostics_store=store)
    except AnalysisError as error:
        print(json.dumps({"error": error.code}))
        return 1
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        started = time.monotonic()
        try:
            result = analyzer.analyze(case["document"], case["id"])
            mismatches = [f for f in FIELDS if result.profile["data"][f] != case["expected"][f]]
            row = {"id": case["id"], "passed": not mismatches, "mismatch_fields": mismatches,
                   "provider_calls": result.provider_calls, "repaired_fields": result.repaired_fields,
                   "first_pass_validated": result.first_pass_validated, "model": result.model, "prompt_tokens": result.prompt_tokens,
                   "completion_tokens": result.completion_tokens, "elapsed_ms": result.elapsed_ms, "diagnostics": result.diagnostics}
        except AnalysisError as error:
            row = {"id": case["id"], "passed": False, "error": error.code, "field": error.field, "provider_calls": error.provider_calls,
                   "first_pass_validated": error.first_pass_validated, "repaired_fields": error.repaired_fields,
                   "elapsed_ms": round((time.monotonic() - started) * 1000), "diagnostics": error.diagnostics}
        rows.append(row)
        print(json.dumps(row), flush=True)
    report = {"case_count": len(rows), "passed": sum(row["passed"] for row in rows),
              "retries": 0, "prompt_version": PROMPT_VERSION, "evidence_contract": CONTRACT_VERSION, "model_requested": "solar-pro4",
              "reasoning_effort": REASONING_EFFORT, "frequency_penalty": FREQUENCY_PENALTY, "temperature": 0, "max_tokens": 4096, "review_reasoning_effort": REVIEW_REASONING_EFFORT, "review_max_tokens": REVIEW_MAX_TOKENS, "cases": rows}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": report["case_count"], "passed": report["passed"]}))
    return 0 if report["passed"] == report["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
