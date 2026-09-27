"""Tuning-only comparison of section embeddings and source candidate recall."""
import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .anchored_candidates import candidate_schema, units, validate_quotes
from .candidate_occurrences import CANDIDATE_EXPANSION_PROMPT
from .sections import batch_sections
from .solar import AnalysisError, SolarAnalyzer, _NoRedirect

MODEL = "nvidia/nemotron-3-embed-1b"
ENDPOINT = "https://integrate.api.nvidia.com/v1/embeddings"
QUERY_TEXTS = (
    "현재 제품의 확정된 프로젝트 이름",
    "현재 제품의 제공 형태 또는 서비스 유형",
    "현재 제품의 분야 또는 도메인",
    "현재 제품의 프론트엔드 기술",
    "현재 제품의 백엔드 기술과 런타임",
    "현재 제품 운영에 채택된 AI 모델",
    "현재 제품의 데이터베이스",
    "현재 제품의 배포 플랫폼",
    "현재 제품의 사용자 및 운영 기능",
    "현재 제품의 외부 연동 제공자",
)
KEYWORDS = (
    ("이름", "명칭", "프로젝트"), ("서비스", "CLI", "앱"),
    ("분야", "교육", "도메인"), ("화면", "프론트엔드"),
    ("서버", "백엔드", "런타임"), ("AI", "모델"),
    ("데이터", "DB", "저장"), ("배포", "운영"),
    ("사용자", "운영자", "기능", "관리자"), ("외부", "제공자", "연동"),
)


def load_cases():
    path = Path(__file__).resolve().parents[2] / "specs/ai-developer/04-analysis-provider/embedding-section-focus/cases.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("version") != "embedding-focus-synthetic-v1" or len(source.get("cases", [])) != 8:
        raise ValueError("invalid frozen cases")
    cases = source["cases"]
    for case in cases:
        paragraphs = case.get("sections")
        if type(paragraphs) is not list or len(paragraphs) != 6 or any(type(x) is not str or not x.strip() for x in paragraphs):
            raise ValueError("invalid sections")
        case["document"] = "\n\n".join(paragraphs)
        source_units = units(case["document"])
        if len(source_units) != len(paragraphs) or any(not s.text.startswith(text) for s, text in zip(source_units, paragraphs)):
            raise ValueError("section mapping changed")
        gold_spans(case)
    return cases, hashlib.sha256(path.read_bytes()).hexdigest()


def gold_spans(case):
    result = []
    sections = case["sections"]
    source_units = units(case["document"])
    for item in case["gold"]:
        index = item["section"]
        quote = item["quote"]
        if type(index) is not int or index not in range(len(sections)) or type(quote) is not str:
            raise ValueError("invalid gold")
        if sections[index].count(quote) != 1:
            raise ValueError("ambiguous gold")
        start = source_units[index].start + sections[index].index(quote)
        result.append((start, start + len(quote)))
    return result


def cosine(a, b):
    if len(a) != len(b) or not a:
        raise ValueError("embedding dimension mismatch")
    aa = math.sqrt(sum(x*x for x in a))
    bb = math.sqrt(sum(x*x for x in b))
    if not aa or not bb:
        raise ValueError("zero embedding")
    return sum(x*y for x, y in zip(a, b)) / (aa*bb)


def rank_sections(queries, passages, k=4):
    scores = [max(cosine(query, passage) for query in queries) for passage in passages]
    return sorted(range(len(passages)), key=lambda i: (-scores[i], i))[:k]


def lexical_sections(passages, k=4):
    scores = [max(sum(word.casefold() in passage.casefold() for word in group) for group in KEYWORDS)
              for passage in passages]
    return sorted(range(len(passages)), key=lambda i: (-scores[i], i))[:k]


def recall_at_k(gold_sections, ranked):
    expected = set(gold_sections)
    return len(expected.intersection(ranked)), len(expected)


def validate_embedding_reply(reply, count, *, dimension=2048):
    if type(reply) is not dict or reply.get("model") != MODEL or type(reply.get("data")) is not list:
        raise ValueError("invalid embedding response")
    data = reply["data"]
    if len(data) != count:
        raise ValueError("embedding count mismatch")
    vectors = []
    for index, item in enumerate(data):
        if type(item) is not dict or item.get("index") != index:
            raise ValueError("embedding order mismatch")
        value = item.get("embedding")
        if type(value) is not list or len(value) != dimension or any(
                type(x) not in (int, float) or not math.isfinite(x) for x in value):
            raise ValueError("invalid embedding vector")
        vectors.append(value)
    return vectors


def embed(key, texts, kind, timeout=30):
    if kind not in ("query", "passage"):
        raise ValueError("invalid input type")
    payload = {"model": MODEL, "input": texts, "input_type": kind, "truncate": "NONE"}
    req = Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    try:
        with build_opener(_NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read(2_000_001)
    except HTTPError as error:
        status = error.code
        error.close()
        raise ValueError("EMBED_AUTH" if status in (401, 403) else
                         "EMBED_RATE_LIMIT" if status == 429 else "EMBED_PROVIDER") from None
    except (TimeoutError, URLError, OSError):
        raise ValueError("EMBED_NETWORK") from None
    if len(raw) > 2_000_000:
        raise ValueError("EMBED_TOO_LARGE")
    try:
        return validate_embedding_reply(json.loads(raw), len(texts))
    except (TypeError, ValueError):
        raise ValueError("EMBED_INVALID") from None


def load_key(name):
    key = os.environ.get(name, "").strip()
    if not key:
        env = Path(__file__).resolve().parents[2] / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith(name + "="):
                    key = line.partition("=")[2].strip().strip('"').strip("'")
                    break
    if not key:
        raise ValueError(name + " missing")
    return key


def _baseline_failure_reason(reply, batch, source_units):
    """Classify a rejected in-memory reply without retaining source or response."""
    if type(reply) is not dict or set(reply) != {"units"} or type(reply["units"]) is not list:
        return "invalid_shape"
    groups = reply["units"]
    if any(type(group) is not dict or set(group) != {"unitId", "quotes"}
           or type(group["unitId"]) is not str for group in groups):
        return "invalid_shape"
    ids = [group["unitId"] for group in groups]
    if len(ids) != len(set(ids)) or set(ids) != {section.id for section in batch}:
        return "id_coverage"
    mapping = {section.id: section for section in batch}
    for group in groups:
        quotes = group["quotes"]
        if (type(quotes) is not list or len(quotes) > 30 or
                any(type(quote) is not str or not quote.strip() or len(quote) > 2000
                    for quote in quotes)):
            return "invalid_quote"
        if len(quotes) != len(set(quotes)):
            return "duplicate_quote"
        for quote in quotes:
            if quote not in mapping[group["unitId"]].text:
                matches = sum(quote in section.text for section in source_units)
                return "not_in_source" if matches == 0 else "wrong_unit" if matches == 1 else "ambiguous_unit"
    return "other"


def candidate_recall(case, key, *, diagnose=False):
    source_units = units(case["document"])
    batches = batch_sections(source_units)
    analyzer = SolarAnalyzer(key, model="solar-pro4")
    spans = []
    calls = 0
    started = time.monotonic()
    try:
        for batch in batches:
            content = {"document_context": {"headings": [list(s.path) for s in source_units], "opening": source_units[0].text},
                       "units": [{"unitId": s.id, "headingPath": list(s.path), "text": s.text,
                                  "previous": source_units[i-1].text if i else None,
                                  "next": source_units[i+1].text if i+1<len(source_units) else None}
                                 for s in batch for i in [source_units.index(s)]]}
            payload = {"model": "solar-pro4", "messages": [
                {"role": "system", "content": CANDIDATE_EXPANSION_PROMPT},
                {"role": "user", "content": json.dumps(content, ensure_ascii=False)}],
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "agentfit_sections", "strict": True, "schema": candidate_schema(batch)}},
                "reasoning_effort": "none", "frequency_penalty": 0,
                "temperature": 0, "max_tokens": 4096, "stream": False}
            trace = {}
            try:
                calls += 1
                reply, _, _, _ = analyzer._send_payload(payload, ("units",), _trace=trace, timeout=40)
            finally:
                trace.pop("raw", None)
            try:
                found = validate_quotes(reply, batch, len(spans), expand_occurrences=True)
            except AnalysisError as error:
                if diagnose and error.code == "ANCHORED_CANDIDATE":
                    error.candidate_detail = {"reason": _baseline_failure_reason(reply, batch, source_units)}
                raise
            spans.extend(found)
        present = [any(item["span"]["start"] <= a and item["span"]["end"] >= b for item in spans)
                   for a, b in gold_spans(case)]
        return {"matched": sum(present), "total": len(present), "candidate_count": len(spans),
                "calls": calls, "elapsed_ms": round((time.monotonic()-started)*1000)}
    except AnalysisError as error:
        result = {"matched": 0, "total": len(case["gold"]), "error": error.code,
                  "calls": calls, "elapsed_ms": round((time.monotonic()-started)*1000)}
        if diagnose and hasattr(error, "candidate_detail"):
            result["reason"] = error.candidate_detail["reason"]
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live required")
    cases, digest = load_cases()
    nvidia_key = load_key("NVIDIA_API_KEY")
    solar_key = load_key("UPSTAGE_API_KEY")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "plan.json").write_text(json.dumps({
        "dataset_sha256": digest, "cases": len(cases), "embedding_model": MODEL,
        "queries": len(QUERY_TEXTS), "top_k": 4, "candidate_model": "solar-pro4",
        "held_out": False}, indent=2), encoding="utf-8")
    query_vectors = embed(nvidia_key, list(QUERY_TEXTS), "query")
    rows = []
    for case in cases:
        started = time.monotonic()
        passages = embed(nvidia_key, case["sections"], "passage")
        embedding = rank_sections(query_vectors, passages)
        lexical = lexical_sections(case["sections"])
        gold = [item["section"] for item in case["gold"]]
        row = {"id": case["id"], "gold_count": len(set(gold)),
               "embedding_selected": embedding, "embedding_recall": recall_at_k(gold, embedding)[0],
               "lexical_selected": lexical, "lexical_recall": recall_at_k(gold, lexical)[0],
               "all_sections_recall": len(set(gold)),
               "embedding_elapsed_ms": round((time.monotonic()-started)*1000)}
        row["candidate"] = candidate_recall(case, solar_key)
        rows.append(row)
        (args.output / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps({"id": row["id"], "embed": row["embedding_recall"],
                          "gold": row["gold_count"], "candidate": row["candidate"]["matched"]}), flush=True)
    return 0 if all(row["embedding_recall"] == row["gold_count"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
