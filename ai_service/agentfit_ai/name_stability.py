"""Fixed synthetic stability evaluation; all attempts count, no retry."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

from .evaluate import CASES, load_api_key
from .profile import FIELDS
from .solar import AnalysisError, SolarAnalyzer, PROMPT_VERSION, SYSTEM_PROMPT, REASONING_EFFORT, FREQUENCY_PENALTY

NEW_CASES = CASES.with_name("name-stability-cases.json")


def evaluate_cases(cases, analyzer, *, repeats=2, workers=2, on_row=None):
    jobs = [(case, repeat) for repeat in range(1, repeats + 1) for case in cases]

    def attempt(job):
        case, repeat = job
        started = time.monotonic()
        row = {"id": case["id"], "repeat": repeat}
        try:
            result = analyzer.analyze(case["document"], case["id"])
            data = result.profile["data"]
            mismatches = [field for field in FIELDS if data[field] != case["expected"][field]]
            name = data["project_name"]
            start = case["document"].find(name) if isinstance(name, str) else -1
            row.update(passed=not mismatches, name_passed="project_name" not in mismatches,
                       mismatch_fields=mismatches,
                       name_span={"start": start, "end": start + len(name)} if start >= 0 else None,
                       provider_calls=getattr(result, "provider_calls", 2),
                       repaired_fields=getattr(result, "repaired_fields", ()),
                       first_pass_validated=getattr(result, "first_pass_validated", True),
                       model=result.model, prompt_tokens=result.prompt_tokens,
                       completion_tokens=result.completion_tokens, elapsed_ms=result.elapsed_ms)
        except AnalysisError as error:
            row.update(passed=False, name_passed=False, error=error.code, field=error.field, provider_calls=error.provider_calls,
                       first_pass_validated=error.first_pass_validated, repaired_fields=error.repaired_fields,
                       elapsed_ms=round((time.monotonic() - started) * 1000))
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(attempt, jobs):
            rows.append(row)
            if on_row:
                on_row(row)
    return {
        "attempts": len(rows), "distinct_cases": len(cases), "repeats": repeats, "retries": 0,
        "passed": sum(row["passed"] for row in rows),
        "name_passed": sum(row["name_passed"] for row in rows),
        "provider_calls": sum(row["provider_calls"] for row in rows),
        "first_pass_validated": sum(row["first_pass_validated"] for row in rows),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        "fixtures_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        "model_requested": "solar-pro4", "reasoning_effort": REASONING_EFFORT, "frequency_penalty": FREQUENCY_PENALTY, "temperature": 0,
        "max_tokens": 4096, "workers": workers, "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required for 24 synthetic analyses (48 to 72 billable calls)")
    # Exclusive creation prevents accidentally replacing earlier failure results.
    try:
        analyzer = SolarAnalyzer(load_api_key())
    except AnalysisError as error:
        print(json.dumps({"error": error.code}))
        return 1
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    cases += json.loads(NEW_CASES.read_text(encoding="utf-8"))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as output:
        report = evaluate_cases(cases, analyzer, on_row=lambda row: print(json.dumps(row), flush=True))
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("attempts", "passed", "name_passed")}))
    return 0 if report["passed"] == report["attempts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
