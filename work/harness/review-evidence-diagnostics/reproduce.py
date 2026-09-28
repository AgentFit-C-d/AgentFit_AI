"""One-off, safe-only reproduction of prior compact review failures."""

import hashlib
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ai_service"))

from agentfit_ai.compact_review_evaluation import ROOT, run_case
from agentfit_ai.embedding_section_evaluation import load_key
from agentfit_ai.keyed_profile_evaluation import load_profile_cases


PRIOR_FAILURES = ("N-004", "E06", "E07")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases, dataset_hashes = load_profile_cases()
    targets = (tuple(case["id"] for case in cases) if args.all else
               tuple(args.case_id) if args.case_id else PRIOR_FAILURES)
    selected = {case["id"]: case for case in cases if case["id"] in targets}
    if set(selected) != set(targets):
        raise RuntimeError("TARGET_SET_CHANGED")
    args.output.mkdir(parents=True, exist_ok=False)
    paths = ("ai_service/agentfit_ai/compact_review.py",
             "ai_service/agentfit_ai/anchored_analysis.py",
             "ai_service/agentfit_ai/semantic_review.py")
    plan = {"cases": list(targets), "dataset_sha256": dataset_hashes,
            "model": "solar-pro4", "overall_timeout_seconds": 60,
            "per_call_cap_seconds": 40, "review_effort": "medium",
            "contract": "compact-review-v1-diagnostic-only",
            "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in paths}}
    (args.output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    key = load_key("UPSTAGE_API_KEY")
    rows = []
    for case_id in targets:
        result = run_case(selected[case_id], key, True)
        rows.append({"id": case_id, "compact": result})
        (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reasons = [call["review_error"]["reason"] for call in result.get("calls", [])
                   if "review_error" in call]
        print(json.dumps({"id": case_id, "error": result.get("error"),
                          "review_reasons": reasons}), flush=True)


if __name__ == "__main__":
    main()
