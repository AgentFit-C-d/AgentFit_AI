"""Fixed synthetic role classification evaluation; no retry or response content output."""
import argparse
import hashlib
import json
from pathlib import Path
from .evaluate import load_api_key
from .solar import SolarAnalyzer, AnalysisError, PROMPT_VERSION
from .diagnostics import LocalDiagnosticsStore

CASES = Path(__file__).resolve().parents[1] / "tests/fixtures/role-classification-cases.json"


def mismatches(data, case):
    failures = []
    for field, expected in case.get("exact", {}).items():
        actual = data.get(field)
        equal = sorted(actual) == sorted(expected) if isinstance(actual, list) and isinstance(expected, list) else actual == expected
        if not equal:
            failures.append(field)
    for rule in ("contains", "forbidden"):
        for field, terms in case.get(rule, {}).items():
            value = data.get(field)
            text = " ".join(value) if isinstance(value, list) else value or ""
            for term in terms:
                if (term not in text) if rule == "contains" else (term in text):
                    failures.append(field + ":" + rule + ":" + term)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 2), default=2)
    parser.add_argument("--diagnostics-dir", type=Path)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required for billable Solar calls")
    store = LocalDiagnosticsStore(args.diagnostics_dir) if args.diagnostics_dir else None
    analyzer = SolarAnalyzer(load_api_key(), diagnostics_store=store)
    fixtures = CASES.read_bytes()
    cases = json.loads(fixtures)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with args.report.open("x", encoding="utf-8") as handle:
        for repeat in range(1, args.repeats + 1):
            for case in cases:
                row = {"id": case["id"], "repeat": repeat}
                try:
                    result = analyzer.analyze(case["document"], case["id"])
                    failures = mismatches(result.profile["data"], case)
                    row.update(passed=not failures, mismatches=failures,
                               first_pass_validated=result.first_pass_validated,
                               provider_calls=result.provider_calls, repaired_fields=result.repaired_fields,
                               diagnostics=result.diagnostics)
                except AnalysisError as error:
                    row.update(passed=False, error=error.code, field=error.field,
                               first_pass_validated=error.first_pass_validated,
                               provider_calls=error.provider_calls, repaired_fields=error.repaired_fields,
                               diagnostics=error.diagnostics)
                rows.append(row)
                print(json.dumps({k:v for k,v in row.items() if k != "diagnostics"}), flush=True)
        report = {"prompt_version": PROMPT_VERSION, "fixtures_sha256": hashlib.sha256(fixtures).hexdigest(),
                  "attempts": len(rows), "passed": sum(row["passed"] for row in rows), "retries": 0,
                  "cases": rows}
        handle.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("attempts", "passed")}))
    return 0 if report["passed"] == report["attempts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
