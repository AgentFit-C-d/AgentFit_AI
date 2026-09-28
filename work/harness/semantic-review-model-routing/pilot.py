"""Synthetic-only NVIDIA compact review compatibility probe."""

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ai_service"))

from agentfit_ai.compact_review import normalize_compact_review, review_payload
from agentfit_ai.deepseek_evaluation import NVIDIA_REVIEW_MODELS, NvidiaAnalyzer, load_key
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.semantic_review import ReviewValidationError
from agentfit_ai.solar import AnalysisError


OUTPUT = ROOT / "specs/ai-developer/04-analysis-provider/semantic-review-model-routing/results/pilot1"


def main():
    document = "현재 제품 이름은 Alpha다."
    start = document.index("Alpha")
    profile = validate_profile(document, "synthetic", {
        "data": {**dict.fromkeys(FIELDS), "project_name": "Alpha"},
        "evidence": {**{field: [] for field in FIELDS},
                     "project_name": [{"start": start, "end": start + 5}]},
    })
    payload = review_payload(document, profile, model="solar-pro4", effort="medium")
    OUTPUT.mkdir(parents=True, exist_ok=False)
    paths = ("ai_service/agentfit_ai/deepseek_evaluation.py",
             "ai_service/agentfit_ai/compact_review.py")
    plan = {"models": list(NVIDIA_REVIEW_MODELS), "synthetic_only": True,
            "timeout_seconds": 40, "schema": "compact-review-v1",
            "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in paths}}
    (OUTPUT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    key = load_key()
    rows = []
    for model in NVIDIA_REVIEW_MODELS:
        started = time.monotonic()
        trace = {}
        row = {"model": model}
        try:
            reply, reported, _, _ = NvidiaAnalyzer(key, model=model)._send_payload(
                payload, ("issues",), _trace=trace, timeout=40)
            issues = normalize_compact_review(reply, profile, document)
            row.update(reported_model=reported, issue_count=len(issues), valid=True)
        except (AnalysisError, ReviewValidationError) as error:
            row.update(error=error.code if isinstance(error, AnalysisError) else "SEMANTIC_REVIEW_INVALID",
                       reason=getattr(error, "reason", None), valid=False)
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        row["provider_elapsed_ms"] = trace.get("provider_elapsed_ms")
        rows.append(row)
        (OUTPUT / "results.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
