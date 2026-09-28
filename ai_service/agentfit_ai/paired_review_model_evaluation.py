"""Tuning-only paired comparison with one shared in-memory extraction and judgment."""

import argparse
import hashlib
import hmac
import json
import os
import secrets
import statistics
import time
from collections import Counter
from pathlib import Path

from .analysis_timeout_evaluation import ReviewCappedAnchoredAnalyzer
from .compact_review_evaluation import review_metrics
from .deepseek_evaluation import MODEL as DEEPSEEK_MODEL, load_key as load_nvidia_key
from .embedding_section_evaluation import load_key as load_solar_key
from .keyed_profile_evaluation import (
    focus_score, full_score, load_profile_cases, summarize, validation_error_count,
)
from .review_model_evaluation import safe_model_diagnostics
from .solar import AnalysisError, post_solar


ROOT = Path(__file__).resolve().parents[2]
ARMS = ("baseline", "compact")


def fingerprint(value, secret):
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return hmac.new(secret, value, hashlib.sha256).hexdigest()


class CaptureTransport:
    def __init__(self, secret, provider=post_solar):
        self.secret = secret
        self.provider = provider
        self.records = []

    def __call__(self, payload, key, timeout):
        raw = self.provider(payload, key, timeout)
        self.records.append((fingerprint(payload, self.secret), raw))
        return raw

    def public_fingerprints(self):
        return [{"request_hmac": request, "response_hmac": fingerprint(raw, self.secret)}
                for request, raw in self.records]


class ReplayMismatch(AnalysisError):
    def __init__(self):
        super().__init__("REPLAY_MISMATCH")


class ReplayTransport:
    def __init__(self, records, secret, provider=post_solar):
        self.records = records
        self.secret = secret
        self.provider = provider
        self.replayed_calls = 0

    def __call__(self, payload, key, timeout):
        if self.replayed_calls == len(self.records):
            return self.provider(payload, key, timeout)
        expected, raw = self.records[self.replayed_calls]
        if fingerprint(payload, self.secret) != expected:
            raise ReplayMismatch()
        self.replayed_calls += 1
        return raw


class DraftCaptured(Exception):
    """Stop before sending the first review; no draft or source leaves this exception."""


class UpstreamOnlyAnalyzer(ReviewCappedAnchoredAnalyzer):
    def _request_review(self, document, profile, *, _trace=None, timeout=40):
        raise DraftCaptured()


def adjusted_deadline(deadline, upstream_ms):
    return deadline - upstream_ms / 1000


class SharedUpstreamAnalyzer(ReviewCappedAnchoredAnalyzer):
    def __init__(self, *args, upstream_ms, **kwargs):
        self.upstream_ms = upstream_ms
        super().__init__(*args, **kwargs)

    def _analyze(self, document, document_id, diagnostic, raw_responses, deadline):
        return super()._analyze(document, document_id, diagnostic, raw_responses,
                                adjusted_deadline(deadline, self.upstream_ms))


def options():
    return {"model": "solar-pro4", "prompt_revision": "v2",
            "candidate_occurrences": True, "keyed_candidates": True,
            "review_effort": "medium", "compact_review": True,
            "analysis_timeout_seconds": 60}


def capture_upstream(case, solar_key, secret, provider=post_solar):
    transport = CaptureTransport(secret, provider)
    analyzer = UpstreamOnlyAnalyzer(solar_key, transport=transport, **options())
    started = time.monotonic()
    try:
        analyzer.analyze(case["document"], case["id"])
    except DraftCaptured:
        return transport, round((time.monotonic() - started) * 1000), None
    except AnalysisError as error:
        return transport, round((time.monotonic() - started) * 1000), {
            "error": error.code, **safe_model_diagnostics(error.diagnostics or {})}
    raise AssertionError("upstream-only analyzer reached a final Profile")


def run_arm(case, solar_key, nvidia_key, arm, records, secret, upstream_ms,
            provider=post_solar):
    transport = ReplayTransport(records, secret, provider)
    routed = arm == "compact"
    review_options = ({"review_model": DEEPSEEK_MODEL, "review_api_key": nvidia_key}
                      if routed else {})
    analyzer = SharedUpstreamAnalyzer(solar_key, transport=transport,
                                      upstream_ms=upstream_ms, **options(), **review_options)
    try:
        result = analyzer.analyze(case["document"], case["id"])
        score = (full_score(result.profile, case["gold"]) if case["kind"] == "full"
                 else focus_score(case, result.profile))
        output = {**score, "provider_calls": result.provider_calls,
                  "first_pass": result.first_pass_validated,
                  **safe_model_diagnostics(result.diagnostics)}
    except AnalysisError as error:
        diagnostic = error.diagnostics or {}
        output = {"error": error.code,
                  "provider_calls": len(diagnostic.get("calls", [])),
                  **safe_model_diagnostics(diagnostic)}
    output["elapsed_ms"] = upstream_ms + output.get("elapsed_ms", 0)
    output["replayed_calls"] = transport.replayed_calls
    output["replay_verified"] = transport.replayed_calls == len(records)
    return output


def aggregate(rows):
    comparable = [row for row in rows if "common_error" not in row]
    shared = Counter(row["common_error"] for row in rows if "common_error" in row)
    groups = {}
    for kind in ("full", "focus"):
        subset = [row for row in comparable if row["kind"] == kind]
        groups[kind] = {arm: summarize(subset, arm) for arm in ARMS}
    reviews = {arm: review_metrics(comparable, arm) for arm in ARMS}
    total = lambda arm, key: sum(row[arm].get(key, 0) for row in comparable)
    validation = lambda arm: sum(validation_error_count(groups[kind][arm])
                                 for kind in groups)
    gate = {
        "all_cases_accounted": len(rows) == 20,
        "shared_upstream_replayed": all(row[arm].get("replay_verified", False)
                                        for row in comparable for arm in ARMS),
        "six_call_limit": all(row[arm].get("provider_calls", 0) <= 6
                              for row in comparable for arm in ARMS),
        "virtual_60s_limit": all(row[arm].get("elapsed_ms", 0) <= 60000
                                 for row in comparable for arm in ARMS),
        "full_accuracy_no_regression": groups["full"]["compact"]["matched"] >= groups["full"]["baseline"]["matched"],
        "focus_accuracy_no_regression": groups["focus"]["compact"]["matched"] >= groups["focus"]["baseline"]["matched"],
        "false_confirmations_no_increase": total("compact", "false_confirmations") <= total("baseline", "false_confirmations"),
        "validation_errors_no_increase": validation("compact") <= validation("baseline"),
        "successes_increase": total("compact", "passed") > total("baseline", "passed"),
    }
    return {"comparable_cases": len(comparable), "shared_failures": dict(shared),
            "groups": groups, "review": reviews, "gate": gate,
            "passed": bool(comparable) and all(gate.values()),
            "total_passed": {arm: total(arm, "passed") for arm in ARMS},
            "total_validation_errors": {arm: validation(arm) for arm in ARMS},
            "median_virtual_ms": {arm: statistics.median(
                [row[arm]["elapsed_ms"] for row in comparable]) if comparable else None
                for arm in ARMS}}


def main():
    parser = argparse.ArgumentParser(description="Same-upstream Solar/DeepSeek review evaluation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    if args.env_file is not None:
        for line in args.env_file.read_text(encoding="utf-8-sig").splitlines():
            for name in ("UPSTAGE_API_KEY", "NVIDIA_API_KEY"):
                if line.startswith(name + "=") and not os.environ.get(name):
                    os.environ[name] = line.partition("=")[2].strip().strip('"').strip("'")
    cases, dataset_hashes = load_profile_cases()
    solar_key = load_solar_key("UPSTAGE_API_KEY")
    nvidia_key = load_nvidia_key()
    args.output.mkdir(parents=True, exist_ok=False)
    secret = secrets.token_bytes(32)
    paths = ("ai_service/agentfit_ai/anchored_analysis.py",
             "ai_service/agentfit_ai/solar.py",
             "ai_service/agentfit_ai/compact_review.py",
             "ai_service/agentfit_ai/paired_review_model_evaluation.py")
    plan = {"cases": len(cases), "dataset_sha256": dataset_hashes,
            "arms": {"baseline": "Solar Pro4", "compact": DEEPSEEK_MODEL},
            "shared_stages": ["candidate_generation", "judgment"],
            "contract": "compact-review-v1", "overall_timeout_seconds": 60,
            "per_call_cap_seconds": 40, "held_out": False,
            "order": "even=baseline,compact; odd=compact,baseline",
            "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in paths}}
    (args.output / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for index, case in enumerate(cases):
        capture, upstream_ms, failure = capture_upstream(case, solar_key, secret)
        arms = ARMS if index % 2 == 0 else ARMS[::-1]
        row = {"id": case["id"], "kind": case["kind"],
               "gold_total": 10 if case["kind"] == "full" else len(case["gold"]),
               "order": list(arms), "upstream_ms": upstream_ms,
               "upstream_fingerprints": capture.public_fingerprints()}
        if failure:
            row["common_error"] = failure["error"]
            for arm in arms:
                row[arm] = {**failure, "provider_calls": len(failure.get("calls", [])),
                            "elapsed_ms": upstream_ms}
        else:
            for arm in arms:
                row[arm] = run_arm(case, solar_key, nvidia_key, arm, capture.records,
                                   secret, upstream_ms)
        rows.append(row)
        (args.output / "results.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"], "shared_error": row.get("common_error"),
                          "solar": row["baseline"].get("matched"),
                          "deepseek": row["compact"].get("matched"),
                          "solar_error": row["baseline"].get("error"),
                          "deepseek_error": row["compact"].get("error")}), flush=True)
    summary = aggregate(rows)
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
