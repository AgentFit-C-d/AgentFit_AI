"""Tuning-only paired comparison of array and keyed candidate contracts."""

import argparse
import json
import statistics
import time
from pathlib import Path

from .anchored_candidates import units
from .candidate_unit_contract import (
    KEYED_CANDIDATE_PROMPT, keyed_candidate_schema, normalize_keyed_candidates,
)
from .embedding_section_evaluation import candidate_recall, gold_spans, load_cases, load_key
from .sections import batch_sections
from .solar import AnalysisError, SolarAnalyzer


def new_candidate_recall(case: dict, key: str) -> dict:
    source_units = units(case["document"])
    batches = batch_sections(source_units)
    analyzer = SolarAnalyzer(key, model="solar-pro4")
    replies = []
    calls = 0
    started = time.monotonic()
    try:
        for batch in batches:
            content = {
                "document_context": {
                    "headings": [list(section.path) for section in source_units],
                    "opening": source_units[0].text,
                },
                "units": [{
                    "unitId": section.id, "headingPath": list(section.path), "text": section.text,
                    "previous": source_units[i - 1].text if i else None,
                    "next": source_units[i + 1].text if i + 1 < len(source_units) else None,
                } for section in batch for i in [source_units.index(section)]],
            }
            payload = {
                "model": "solar-pro4",
                "messages": [
                    {"role": "system", "content": KEYED_CANDIDATE_PROMPT},
                    {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "agentfit_sections", "strict": True,
                    "schema": keyed_candidate_schema(batch),
                }},
                "reasoning_effort": "none", "frequency_penalty": 0,
                "temperature": 0, "max_tokens": 4096, "stream": False,
            }
            trace = {}
            try:
                calls += 1
                reply, _, _, _ = analyzer._send_payload(payload, ("units",), _trace=trace, timeout=40)
            finally:
                trace.pop("raw", None)
            replies.append(reply)
        pool, metrics = normalize_keyed_candidates(replies, batches, source_units)
        gold = gold_spans(case)
        matched = sum(any(item["span"]["start"] <= start and item["span"]["end"] >= end
                          for item in pool) for start, end in gold)
        return {"matched": matched, "total": len(gold), "candidate_count": len(pool),
                "calls": calls, "elapsed_ms": round((time.monotonic() - started) * 1000),
                **metrics}
    except AnalysisError as error:
        result = {"matched": 0, "total": len(case["gold"]), "error": error.code,
                  "calls": calls, "elapsed_ms": round((time.monotonic() - started) * 1000)}
        if hasattr(error, "candidate_detail"):
            result["reason"] = error.candidate_detail["reason"]
        return result


def _arm_summary(rows, arm):
    results = [row[arm] for row in rows]
    valid = [result for result in results if "error" not in result]
    errors = {}
    for result in results:
        if "error" in result:
            name = result["error"] + (":" + result["reason"] if "reason" in result else "")
            errors[name] = errors.get(name, 0) + 1
    times = sorted(result["elapsed_ms"] for result in results)
    return {"valid_cases": len(valid), "matched_in_valid": sum(item["matched"] for item in valid),
            "gold_in_valid": sum(item["total"] for item in valid), "errors": errors,
            "max_calls": max(item["calls"] for item in results),
            "median_ms": statistics.median(times),
            "p95_ms": times[max(0, (95 * len(times) + 99) // 100 - 1)]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, digest = load_cases()
    key = load_key("UPSTAGE_API_KEY")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "plan.json").write_text(json.dumps({
        "dataset_sha256": digest, "cases": len(cases), "model": "solar-pro4",
        "order": "even=baseline,new; odd=new,baseline", "held_out": False,
        "gate": {"new_valid_cases": 8, "new_gold_matched": 27,
                 "new_max_calls": 2, "no_source_errors": True,
                 "no_regression_vs_baseline": True},
    }, indent=2) + "\n", encoding="utf-8")
    rows = []
    for index, case in enumerate(cases):
        arms = ("baseline", "new") if index % 2 == 0 else ("new", "baseline")
        row = {"id": case["id"], "gold_count": len(case["gold"]), "order": list(arms)}
        for arm in arms:
            row[arm] = candidate_recall(case, key, diagnose=True) if arm == "baseline" else new_candidate_recall(case, key)
        rows.append(row)
        (args.output / "results.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"], "baseline": row["baseline"]["matched"],
                          "new": row["new"]["matched"]}), flush=True)
    baseline = _arm_summary(rows, "baseline")
    new = _arm_summary(rows, "new")
    gate = {"new_valid_all": new["valid_cases"] == 8,
            "new_all_gold": new["matched_in_valid"] == 27,
            "new_no_source_errors": not any(name.startswith(("ANCHORED_CANDIDATE", "SECTION_LIMIT"))
                                            for name in new["errors"]),
            "new_call_budget": new["max_calls"] <= 2,
            "no_regression_vs_baseline": (new["valid_cases"] >= baseline["valid_cases"]
                                           and new["matched_in_valid"] >= baseline["matched_in_valid"])}
    (args.output / "summary.json").write_text(json.dumps({
        "cases": len(cases), "gold": sum(row["gold_count"] for row in rows),
        "baseline": baseline, "new": new, "gate": gate,
        "passed": all(gate.values()),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(gate.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
