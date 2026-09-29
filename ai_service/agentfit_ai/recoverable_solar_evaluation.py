"""One-pass synthetic evaluation of opt-in recoverable Solar outcomes."""

import argparse
import hashlib
import json
from pathlib import Path

from .false_complete_evaluation import write_safe_json
from .keyed_profile_evaluation import load_profile_cases
from .recoverable_draft_evaluation import ROOT, aggregate, load_key, run_case
from .recoverable_solar_analysis import RecoverableSolarAnalyzer
from .solar import post_solar_inline


CODE_PATHS = (
    "ai_service/agentfit_ai/solar.py",
    "ai_service/agentfit_ai/recoverable_draft.py",
    "ai_service/agentfit_ai/recoverable_solar_analysis.py",
    "ai_service/agentfit_ai/recoverable_solar_evaluation.py",
)


def solar_factory(key, *, transport, **_anchored_options):
    return RecoverableSolarAnalyzer(
        key, transport=transport, model="solar-pro4", evidence_contract=True,
        semantic_review=True, analysis_timeout_seconds=40)


def main():
    parser = argparse.ArgumentParser(description="Recoverable Solar synthetic evaluation")
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
    plan = {"model": "solar-pro4", "analysis_timeout_seconds": 40,
            "semantic_review": True, "evidence_contract": True,
            "selected_case_ids": [case["id"] for case in cases],
            "held_out": False, "dataset_sha256": hashes,
            "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in CODE_PATHS}}
    write_safe_json(args.output / "plan.json", plan, forbidden_strings=forbidden)
    rows = []
    write_safe_json(args.output / "results.json", rows, forbidden_strings=forbidden)
    for case in cases:
        row = run_case(case, key, provider=post_solar_inline,
                       analyzer_factory=solar_factory)
        rows.append(row)
        write_safe_json(args.output / "results.json", rows, forbidden_strings=forbidden)
        write_safe_json(args.output / "summary.json", aggregate(rows, planned=len(cases)),
                        forbidden_strings=forbidden)
        print(json.dumps({"id": row["id"], "outcome": row["outcome"],
                          "error": row["error"], "suggested_fields": row["suggested_fields"],
                          "questions": row["questions"],
                          "false_confirmations": row["false_confirmations"],
                          "elapsed_ms": row["elapsed_ms"]}), flush=True)
    return 0 if aggregate(rows, planned=len(cases))["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
