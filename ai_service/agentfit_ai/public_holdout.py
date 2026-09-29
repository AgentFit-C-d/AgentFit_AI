"""Pinned public documents and conservative, partial Profile scoring."""

import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from .profile import ARRAY_FIELDS, FIELDS


MAX_DOCUMENT_BYTES = 100_000
MANIFEST = (Path(__file__).resolve().parents[2] /
            "specs/ai-developer/04-analysis-provider/public-holdout-corpus/manifest.json")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_PATH = re.compile(r"[A-Za-z0-9_./-]+\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _check_case(case):
    if (type(case) is not dict or set(case) !=
            {"id", "repo", "commit", "path", "sha256", "checks"}):
        raise ValueError("invalid public case")
    if (type(case["id"]) is not str or not re.fullmatch(r"[a-z0-9-]{1,64}", case["id"])
            or type(case["repo"]) is not str or not _REPO.fullmatch(case["repo"])
            or any(part in (".", "..") for part in case["repo"].split("/"))
            or type(case["commit"]) is not str or not _HEX40.fullmatch(case["commit"])
            or type(case["path"]) is not str or not _PATH.fullmatch(case["path"])
            or any(part in ("", ".", "..") for part in case["path"].split("/"))
            or type(case["sha256"]) is not str or not _HEX64.fullmatch(case["sha256"])):
        raise ValueError("invalid public case source")
    checks = case["checks"]
    if type(checks) is not dict or not checks or not set(checks) <= set(FIELDS):
        raise ValueError("invalid public checks")
    for items in checks.values():
        if type(items) is not list or not items:
            raise ValueError("invalid public checks")
        for item in items:
            if (type(item) is not dict or set(item) != {"aliases", "quote"}
                    or type(item["quote"]) is not str or not 5 <= len(item["quote"]) <= 200
                    or type(item["aliases"]) is not list or not item["aliases"]
                    or any(type(alias) is not str or not alias.strip() or len(alias) > 200
                           for alias in item["aliases"])):
                raise ValueError("invalid public check")


def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if type(data) is not dict or set(data) != {"version", "partition", "cases"}:
        raise ValueError("invalid public manifest")
    if data["version"] != "public-holdout-v1" or data["partition"] != "tuning":
        raise ValueError("invalid public manifest")
    cases = data["cases"]
    if type(cases) is not list or not cases or any(type(case) is not dict
                                                  for case in cases):
        raise ValueError("invalid public cases")
    for case in cases:
        _check_case(case)
    if len(cases) != len({case["id"] for case in cases}):
        raise ValueError("duplicate public case")
    return cases


def verify_document(case, body):
    _check_case(case)
    if type(body) is not bytes or len(body) > MAX_DOCUMENT_BYTES:
        raise ValueError("invalid public document size")
    if hashlib.sha256(body).hexdigest() != case["sha256"]:
        raise ValueError("public document hash mismatch")
    try:
        document = body.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("invalid public document encoding") from None
    for items in case["checks"].values():
        for item in items:
            if document.count(item["quote"]) != 1:
                raise ValueError("public check quote missing or ambiguous")
    return document


def fetch_document(case):
    _check_case(case)
    url = ("https://raw.githubusercontent.com/" + case["repo"] + "/" +
           case["commit"] + "/" + case["path"])
    request = Request(url, headers={"User-Agent": "AgentFit-public-holdout/1"})
    with urlopen(request, timeout=15) as response:
        body = response.read(MAX_DOCUMENT_BYTES + 1)
    return verify_document(case, body)


def _covered(document, spans, quote):
    start = document.index(quote)
    end = start + len(quote)
    return any(type(span) is dict and type(span.get("start")) is int
               and type(span.get("end")) is int
               and span["start"] <= start and span["end"] >= end
               for span in spans)


def _matches(value, aliases):
    return any(alias.casefold() in value.casefold() for alias in aliases)


def score_profile(case, document, profile):
    """Score only written checks; extra output remains explicitly unassessed."""
    if type(profile) is not dict or type(profile.get("data")) is not dict or type(
            profile.get("evidence")) is not dict:
        raise ValueError("invalid public profile")
    data, evidence = profile["data"], profile["evidence"]
    if set(data) != set(FIELDS) or set(evidence) != set(FIELDS):
        raise ValueError("invalid public profile")
    matched = wrong_evidence = missing_alias = unassessed = 0
    for field in FIELDS:
        value = data[field]
        values = [] if value is None else value if field in ARRAY_FIELDS else [value]
        if type(values) is not list or any(type(item) is not str for item in values):
            raise ValueError("invalid public profile")
        spans = evidence[field]
        if type(spans) is not list:
            raise ValueError("invalid public profile")
        checks = case["checks"].get(field, [])
        for check in checks:
            if not any(_matches(item, check["aliases"]) for item in values):
                missing_alias += 1
            elif not _covered(document, spans, check["quote"]):
                wrong_evidence += 1
            else:
                matched += 1
        unassessed += sum(not any(_matches(item, check["aliases"])
                                  for check in checks) for item in values)
    return {"total_checks": sum(len(items) for items in case["checks"].values()),
            "matched_checks": matched, "wrong_evidence_checks": wrong_evidence,
            "missing_alias_checks": missing_alias, "unassessed_values": unassessed}
