"""Paired, source-free model probe for one section feature review."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from .deepseek_evaluation import (NVIDIA_REVIEW_MODELS, NvidiaAnalyzer,
                                  load_key as nvidia_load_key, post_nvidia)
from .diagnostics import safe_code
from .false_complete_evaluation import write_safe_json
from .public_holdout import fetch_document, load_manifest
from .recoverable_draft_evaluation import load_key
from .section_feature_review import (normalize_section_review,
                                     section_review_payload, split_feature_sections)
from .semantic_review import ReviewValidationError
from .solar import AnalysisError, SolarAnalyzer, post_solar_inline
from .source_selector_analysis import SourceSelectorSolarAnalyzer


TUNING_MANIFEST = (Path(__file__).resolve().parents[2] /
                   "specs/ai-developer/04-analysis-provider/public-prd-holdout/manifest.json")
CASE_ID = "campfire-prd"

class _DraftCaptured(Exception):
    pass


class _DraftObserver(SourceSelectorSolarAnalyzer):
    def _observe_profile(self, stage, profile):
        if stage == "pre_review":
            self.captured_profile = profile
            raise _DraftCaptured


def capture_draft(document, document_id, key, transport):
    analyzer = _DraftObserver(
        key, transport=transport, semantic_review=True, evidence_contract=True,
        analysis_timeout_seconds=2400, field_call_timeout_seconds=120,
        experimental_long_timeout=True, grouped_review=True,
        group_review_max_tokens=8192, section_feature_review=True,
        section_feature_extraction=True, section_feature_curation=True,
        fieldwise_review=True, fine_feature_review=True)
    try:
        analyzer.analyze(document, document_id)
    except _DraftCaptured:
        return analyzer.captured_profile
    raise AnalysisError("SEMANTIC_REVIEW_INVALID")


def _count(value):
    return value if type(value) is int and value >= 0 else None


def evaluate_section(document, profile, chunk, sender, payload, *, model, effort):
    if (model != "solar-pro4" and model not in NVIDIA_REVIEW_MODELS or
            effort not in ("medium", "low", "none", "provider_default")):
        raise ValueError("unsupported probe arm")
    started = time.monotonic()
    trace = {}
    row = {"model": model, "effort": effort, "outcome": "failed",
           "error": None, "prompt_tokens": None, "completion_tokens": None,
           "elapsed_ms": None, "issue_count": None}
    try:
        reply, _, prompt_tokens, completion_tokens = sender._send_payload(
            payload, ("checkedRange", "issues"), _trace=trace, timeout=600)
        normalized = normalize_section_review(reply, profile, document, chunk)
    except AnalysisError as error:
        row["error"] = safe_code(error.code)
    except ReviewValidationError:
        row["error"] = "SEMANTIC_REVIEW_INVALID"
    except Exception:
        row["error"] = "PROBE_FAILURE"
    else:
        row["outcome"] = "validated"
        row["issue_count"] = len(normalized["issues"])
        row["prompt_tokens"] = _count(prompt_tokens)
        row["completion_tokens"] = _count(completion_tokens)
    finally:
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        if row["prompt_tokens"] is None:
            row["prompt_tokens"] = _count(trace.get("prompt_tokens"))
        if row["completion_tokens"] is None:
            row["completion_tokens"] = _count(trace.get("completion_tokens"))
        trace.pop("raw", None)
    return row


def probe_arms(base_payload):
    arms = []
    for effort in ("medium", "low", "none"):
        payload = deepcopy(base_payload)
        payload["reasoning_effort"] = effort
        arms.append(("solar-pro4", effort, payload))
    for model in NVIDIA_REVIEW_MODELS:
        arms.append((model, "provider_default", deepcopy(base_payload)))
    return tuple(arms)


def main():
    parser = argparse.ArgumentParser(description="Source-free section review model probe")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--manifest", type=Path, default=TUNING_MANIFEST)
    parser.add_argument("--section-index", type=int, default=12)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    if args.output.exists():
        parser.error("output already exists")
    cases = load_manifest(args.manifest, expected_partition="tuning")
    case = next((case for case in cases if case["id"] == CASE_ID), None)
    if case is None:
        parser.error("pinned case missing")
    document = fetch_document(case)
    chunks = split_feature_sections(document, max_lines=50)
    if not 1 <= args.section_index <= len(chunks):
        parser.error("invalid section index")
    chunk = chunks[args.section_index - 1]
    solar_key = load_key(args.env_file)
    nvidia_key = nvidia_load_key(args.env_file)
    forbidden = (document, solar_key, nvidia_key)
    result = {"case_id": CASE_ID,
              "source_sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
              "section_index": args.section_index,
              "section_start": chunk[0], "section_end": chunk[1],
              "total_sections": len(chunks), "arms": [], "outcome": "failed"}
    try:
        profile = capture_draft(document, CASE_ID, solar_key, post_solar_inline)
    except AnalysisError as error:
        result["error"] = safe_code(error.code)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_safe_json(args.output, result, forbidden_strings=forbidden)
        return 1
    result["selected_feature_count"] = (len(profile["data"]["features"])
                                        if type(profile["data"]["features"]) is list
                                        else 0)
    base_payload = section_review_payload(document, profile, chunk,
                                          model="solar-pro4", effort="medium")
    result["outcome"] = "running"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_safe_json(args.output, result, forbidden_strings=forbidden)
    for model, effort, payload in probe_arms(base_payload):
        sender = (SolarAnalyzer(solar_key, transport=post_solar_inline)
                  if model == "solar-pro4" else
                  NvidiaAnalyzer(nvidia_key, transport=post_nvidia, model=model))
        row = evaluate_section(document, profile, chunk, sender, payload,
                               model=model, effort=effort)
        result["arms"].append(row)
        write_safe_json(args.output, result, forbidden_strings=forbidden)
        print(json.dumps({"model": model, "effort": effort,
                          "outcome": row["outcome"], "error": row["error"],
                          "elapsed_ms": row["elapsed_ms"]}), flush=True)
    result["outcome"] = "completed"
    write_safe_json(args.output, result, forbidden_strings=forbidden)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
