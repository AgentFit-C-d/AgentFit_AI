"""Conservative value and source-location checks for frozen synthetic cases."""

import json
from pathlib import Path

from .profile import ARRAY_FIELDS, FIELDS
from .repair_observation import score_profile


ORACLE_PATH = (Path(__file__).resolve().parents[2] /
               "specs/ai-developer/04-analysis-provider/synthetic-evidence-oracle/oracle.json")


def _valid_quote(document, quote):
    return type(quote) is str and bool(quote) and quote in document


def load_oracle(cases, path=ORACLE_PATH):
    source = json.loads(path.read_text(encoding="utf-8"))
    if (type(source) is not dict or set(source) != {"version", "partition", "held_out", "cases"}
            or source["version"] != "synthetic-evidence-v1" or source["partition"] != "tuning"
            or source["held_out"] is not False or type(source["cases"]) is not dict
            or len(cases) != 20 or len({case["id"] for case in cases}) != 20
            or set(source["cases"]) != {case["id"] for case in cases}):
        raise ValueError("invalid synthetic oracle")
    for case in cases:
        entry = source["cases"][case["id"]]
        if type(entry) is not dict:
            raise ValueError("invalid synthetic oracle case")
        if case["kind"] == "full":
            evidence = entry.get("evidence")
            if (set(entry) != {"evidence"} or type(evidence) is not dict
                    or set(evidence) != set(case["gold"])):
                raise ValueError("invalid full-case evidence")
            for field, quotes in evidence.items():
                expected = case["gold"][field]
                needed = len(expected) if type(expected) is list and expected else 1
                if (field not in FIELDS or type(quotes) is not list or len(quotes) != needed
                        or not all(_valid_quote(case["document"], quote) for quote in quotes)):
                    raise ValueError("invalid full-case quote")
        elif case["kind"] == "focus":
            fields = entry.get("fields")
            if set(entry) != {"fields"} or type(fields) is not dict or not fields:
                raise ValueError("invalid focus-case fields")
            for field, expected in fields.items():
                if field not in FIELDS:
                    raise ValueError("invalid focus-case field")
                if expected is None:
                    continue
                if type(expected) is dict and set(expected) == {"absent"}:
                    if field not in ARRAY_FIELDS or not _valid_quote(
                            case["document"], expected["absent"]):
                        raise ValueError("invalid absence evidence")
                    continue
                if (type(expected) is not list or not expected or
                        (field not in ARRAY_FIELDS and len(expected) != 1)):
                    raise ValueError("invalid focus-case values")
                for item in expected:
                    if (type(item) is not dict or set(item) != {"aliases", "quote"}
                            or type(item["aliases"]) is not list or not item["aliases"]
                            or any(type(alias) is not str or not alias.strip()
                                   for alias in item["aliases"])
                            or not _valid_quote(case["document"], item["quote"])):
                        raise ValueError("invalid focus-case item")
        else:
            raise ValueError("invalid case kind")
    return source["cases"]


def _covers(document, spans, quote):
    start = 0
    while True:
        start = document.find(quote, start)
        if start < 0:
            return False
        end = start + len(quote)
        if any(span["start"] <= start and span["end"] >= end for span in spans):
            return True
        start += 1


def _matches_groups(values, groups):
    if len(values) != len(groups):
        return False
    used = set()

    def match(index):
        if index == len(groups):
            return True
        for position, value in enumerate(values):
            if position not in used and value in groups[index]["aliases"]:
                used.add(position)
                if match(index + 1):
                    return True
                used.remove(position)
        return False

    return match(0)


def assess_profile(case, profile, oracle):
    entry = oracle[case["id"]]
    suggested = {field for field in FIELDS if profile["data"][field] is not None}
    known = set(FIELDS) if case["kind"] == "full" else set(entry["fields"])
    full_score = score_profile(profile, case["gold"]) if case["kind"] == "full" else None
    wrong_values = set()
    wrong_evidence = set()
    missing = set()
    for field in known:
        actual = profile["data"][field]
        if case["kind"] == "full":
            expected = case["gold"].get(field)
            if actual is None:
                if expected is not None:
                    missing.add(field)
                continue
            if not full_score["fields"][field]["matched"]:
                wrong_values.add(field)
                continue
            quotes = entry["evidence"].get(field, [])
        else:
            expected = entry["fields"][field]
            if actual is None:
                if expected is not None:
                    missing.add(field)
                continue
            if expected is None:
                wrong_values.add(field)
                continue
            if type(expected) is dict:
                matched = actual == []
                quotes = [expected["absent"]]
            else:
                values = actual if field in ARRAY_FIELDS and type(actual) is list else [actual]
                matched = _matches_groups(values, expected)
                quotes = [item["quote"] for item in expected]
            if not matched:
                wrong_values.add(field)
                continue
        if any(not _covers(case["document"], profile["evidence"][field], quote)
               for quote in quotes):
            wrong_evidence.add(field)
    unassessed = suggested - known
    return {"assessed_suggested_fields": len(suggested & known),
            "unassessed_suggested_fields": len(unassessed),
            "wrong_value_fields": len(wrong_values),
            "wrong_evidence_fields": len(wrong_evidence),
            "missing_expected_fields": len(missing)}
