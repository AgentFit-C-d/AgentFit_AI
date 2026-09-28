"""Isolated DeepSeek V4.1 Flash evaluation on frozen synthetic candidates."""
import argparse
import copy
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .atomic_evaluation import evaluate_case
from .candidate_occurrence_evaluation import fixed_pool
from .solar import AnalysisError, MAX_RESPONSE_BYTES, SolarAnalyzer, _NoRedirect

MODEL = "deepseek-ai/deepseek-v4.1-flash"
NVIDIA_REVIEW_MODELS = (MODEL, "z-ai/glm-5.3", "moonshotai/kimi-k3")
ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"


def nvidia_payload(source, *, model=MODEL):
    if model not in NVIDIA_REVIEW_MODELS:
        raise ValueError("unsupported NVIDIA model")
    payload = copy.deepcopy(source)
    payload["model"] = model
    payload.pop("frequency_penalty", None)
    if model == MODEL:
        payload.pop("reasoning_effort", None)
        payload["chat_template_kwargs"] = {"thinking": False}
    elif model == "z-ai/glm-5.3":
        payload["reasoning_effort"] = "low"
        payload["chat_template_kwargs"] = {"clear_thinking": True}
        payload["temperature"] = 0.5
    else:
        payload["reasoning_effort"] = "low"
        payload["temperature"] = 1
    return payload


def post_nvidia(payload, api_key, timeout):
    request = Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), headers={
        "Authorization": "Bearer " + api_key, "Content-Type": "application/json",
        "Accept": "application/json"}, method="POST")
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        status = error.code
        error.close()
        code = ("PROVIDER_AUTH" if status in (401, 403) else
                "PROVIDER_RATE_LIMIT" if status == 429 else
                "PROVIDER_REDIRECT" if 300 <= status < 400 else
                "PROVIDER_UNAVAILABLE" if status >= 500 else "PROVIDER_REQUEST")
        raise AnalysisError(code) from None
    except (TimeoutError, URLError, OSError) as error:
        reason = error.reason if isinstance(error, URLError) else error
        raise AnalysisError("PROVIDER_TIMEOUT" if isinstance(reason, TimeoutError)
                            else "PROVIDER_NETWORK") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise AnalysisError("RESPONSE_TOO_LARGE")
    return raw


class NvidiaAnalyzer:
    def __init__(self, key, transport=post_nvidia, *, model=MODEL):
        if model not in NVIDIA_REVIEW_MODELS:
            raise ValueError("unsupported NVIDIA model")
        self._model = model
        self._solar_parser = SolarAnalyzer(key, transport=transport)

    def _send_payload(self, source, names, *, _trace=None, timeout=40):
        payload = nvidia_payload(source, model=self._model)
        # The shared parser expects this trace field and validates the JSON body.
        parser_payload = dict(payload, reasoning_effort="none")
        transport = self._solar_parser._transport
        def checked_transport(_payload, key, limit):
            raw = transport(payload, key, limit)
            try:
                reported_model = json.loads(raw).get("model")
            except (TypeError, ValueError, AttributeError):
                reported_model = None
            if reported_model != self._model:
                raise AnalysisError("PROVIDER_MODEL")
            return raw
        try:
            self._solar_parser._transport = checked_transport
            reply, _model, pt, ct = self._solar_parser._send_payload(
                parser_payload, names, _trace=_trace, timeout=timeout)
        finally:
            self._solar_parser._transport = transport
        if _trace is not None:
            _trace["model"] = self._model
        return reply, self._model, pt, ct


def load_key():
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        env = Path(__file__).resolve().parents[2] / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith("NVIDIA_API_KEY="):
                    key = line.partition("=")[2].strip().strip('"').strip("'")
                    break
    if not key:
        raise ValueError("NVIDIA_API_KEY missing")
    return key


def load_cases():
    root = Path(__file__).resolve().parents[2] / "specs/ai-developer/04-analysis-provider"
    case_path = root / "candidate-occurrence-expansion/evaluation-cases.json"
    extra_path = root / "atomic-candidate-verdict/counterexamples.json"
    gold_path = root / "atomic-candidate-verdict/conflict-gold.json"
    dataset = json.loads(case_path.read_text(encoding="utf-8"))
    extra = json.loads(extra_path.read_text(encoding="utf-8"))
    conflict = json.loads(gold_path.read_text(encoding="utf-8"))
    if hashlib.sha256(case_path.read_bytes()).hexdigest() != extra["existing27_sha256"]:
        raise ValueError("frozen case hash mismatch")
    for name, digest in dataset["source_hashes"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source hash mismatch")
    cases = dataset["cases"] + extra["cases"]
    for case in cases:
        fixed_pool(case)
        if case.get("expected_kind") == "conflict":
            case["expected_conflict_decisions"] = conflict[case["id"]]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (case_path, extra_path, gold_path)}
    return cases, hashes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, hashes = load_cases()
    key = load_key()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "plan.json").write_text(json.dumps({
        "scope": "frozen_synthetic_atomic_judgment", "model": MODEL,
        "thinking": False, "schema": "atomic", "max_tokens": 4096,
        "timeout": 40, "planned_cases": len(cases), "planned_calls": len(cases),
        "case_hashes": hashes, "held_out": False}, indent=2), encoding="utf-8")
    analyzer = NvidiaAnalyzer(key)
    rows = []
    for case in cases:
        if rows:
            time.sleep(2)
        row = evaluate_case(analyzer, case, True)
        row["model"] = MODEL
        rows.append(row)
        (args.output / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps({k: row[k] for k in ("id", "passed", "error", "elapsed_ms") if k in row}), flush=True)
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
