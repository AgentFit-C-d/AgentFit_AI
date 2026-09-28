"""Pure, source-free stage classification for detected false completions."""

import json
from pathlib import Path

from .embedding_section_evaluation import gold_spans
from .keyed_profile_evaluation import full_score
from .profile import FIELDS
from .repair_observation import score_profile


ANNOTATIONS = (Path(__file__).resolve().parents[2] /
               "specs/ai-developer/04-analysis-provider/false-complete-diagnostics/gold-evidence.json")


def load_gold_evidence(cases: list[dict]) -> dict[str, dict[str, list[tuple[int, int]]]]:
    annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in cases}
    if len(by_id) != len(cases) or not set(annotations) <= set(by_id):
        raise ValueError("invalid evidence case id")
    result = {}
    for case_id, fields in annotations.items():
        document = by_id[case_id]["document"]
        result[case_id] = {}
        for field, quotes in fields.items():
            if field not in FIELDS or not quotes or any(
                    not isinstance(quote, str) or not quote or document.count(quote) != 1
                    for quote in quotes):
                raise ValueError("ambiguous evidence annotation")
            result[case_id][field] = [
                (document.index(quote), document.index(quote) + len(quote))
                for quote in quotes
            ]
    for case in cases:
        if case["kind"] == "focus":
            spans = gold_spans(case)
            grouped = result.setdefault(case["id"], {})
            for item, span in zip(case["gold"], spans):
                grouped.setdefault(item["field"], []).append(span)
    return result


def _false_fields(case, profile):
    if case["kind"] == "full":
        score = full_score(profile, case["gold"])
        return [(field, False) for field in score["mismatch_fields"]
                if profile["data"][field] is not None]
    found = set()
    ambiguous = False
    for word in case.get("forbidden", []):
        owners = [field for field in FIELDS
                  if any(word in value for value in (
                      profile["data"][field] if type(profile["data"][field]) is list
                      else [profile["data"][field]] if type(profile["data"][field]) is str
                      else []))]
        if len(owners) == 1:
            found.add(owners[0])
        elif len(owners) > 1:
            ambiguous = True
    return [(field, True) for field in sorted(found)] + ([(None, True)] if ambiguous else [])


def _field_correct(case, profile, field, forbidden):
    if forbidden:
        return not any(word in value for word in case.get("forbidden", [])
                       for value in (profile["data"][field]
                                     if type(profile["data"][field]) is list
                                     else [profile["data"][field]]
                                     if type(profile["data"][field]) is str else []))
    return score_profile(profile, case["gold"])["fields"][field]["matched"]


def _review_detected(observation, stage, field):
    for name, issues in observation.get("reviews", []):
        if name == stage:
            return any(issue["field"] == field for issue in issues)
    return None


def _candidate_capacity_covers(spans, candidates):
    """Each selected candidate can represent at most one expected item."""
    owners = {}

    def assign(span_index, seen):
        start, end = spans[span_index]
        for index, candidate in enumerate(candidates):
            if (index not in seen and candidate["start"] <= start
                    and candidate["end"] >= end):
                seen.add(index)
                if index not in owners or assign(owners[index], seen):
                    owners[index] = span_index
                    return True
        return False

    return all(assign(index, set()) for index in range(len(spans)))


def diagnose_case(case: dict, result: dict, observation: dict,
                  gold_evidence: dict, *, classify_stages: bool = True) -> list[dict]:
    if result.get("outcome") != "complete":
        return []
    profile = result["profile"]
    stages = dict(observation.get("profiles", []))
    candidates = observation.get("candidates", [])
    annotations = gold_evidence.get(case["id"], {})
    rows = []
    for field, forbidden in _false_fields(case, profile):
        category = "undetermined"
        review_stage = None
        if classify_stages and field is not None and "judgment" in stages:
            initial_correct = _field_correct(case, stages["judgment"], field, forbidden)
            if initial_correct:
                if any(stage in stages for stage in ("semantic_repair", "source_repair")):
                    category = "repair_regression"
                    review_stage = "semantic_recheck"
            else:
                review_stage = "semantic_review"
                spans = annotations.get(field, [])
                if spans and not _candidate_capacity_covers(spans, candidates):
                    category = "candidate_gap"
                elif spans or forbidden or case["gold"].get(field) == []:
                    category = "judgment_mismatch"
        evidence = profile.get("evidence", {}).get(field, []) if field else []
        rows.append({
            "field": field,
            "first_observed_divergence": category,
            "review_detected": _review_detected(observation, review_stage, field)
                               if review_stage else None,
            "candidate_ids": [item["id"] for item in candidates] if field else [],
            "candidate_spans": [
                {"id": item["id"], "start": item["start"], "end": item["end"]}
                for item in candidates] if field else [],
            "gold_spans": [{"start": start, "end": end}
                           for start, end in annotations.get(field, [])] if field else [],
            "evidence_spans": [{"start": span["start"], "end": span["end"]}
                               for span in evidence],
        })
    return rows
