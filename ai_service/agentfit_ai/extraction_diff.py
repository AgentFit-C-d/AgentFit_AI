"""Exact-match diagnostics for validated extraction pools, not a semantic judge."""
from collections import Counter, defaultdict
from .evidence import ROLES
from .profile import FIELDS

DIMENSIONS = ("field", "role", "status", "scope")
ALLOWED = {
    "field": set(FIELDS),
    "role": {r for roles in ROLES.values() for r in roles} |
            {"development_task", "technical_description", "client", "generic_source"},
    "status": {"confirmed", "tentative", "negated", "historical", "absent"},
    "scope": {"current", "other", "example", "unclear"},
}

def diagnose(pool, case):
    """Input pool has passed validate_candidates. Never serialize free-form values."""
    absence = "expected_absent" in case
    if "expected" in case:
        expected = [dict(zip(("field", "value", "role", "status", "scope"), row))
                    for row in case["expected"]]
        dimensions = list(DIMENSIONS)
    elif absence:
        expected = [{"field": field, "value": None, "status": "absent", "scope": "current"}
                    for field in case["expected_absent"]]
        dimensions = ["role", "status", "scope"]
    else:
        expected = [{"value": value, "role": role} for value, role in case["expected_roles"].items()]
        dimensions = ["role"]

    key = "field" if absence else "value"
    eg, ag = defaultdict(list), defaultdict(list)
    for index, item in enumerate(expected):
        eg[item[key]].append((index, item))
    for index, item in enumerate(pool):
        ag[item[key]].append((index, item))
    counts = {"missing_exact": 0, "extra_exact": 0, **{d: 0 for d in dimensions},
              "context": 0, "forbidden_confirmed": 0}
    if absence:
        counts["absence_value"] = 0
    groups = []
    for value in dict.fromkeys([*eg, *ag]):
        e, a = eg[value], ag[value]
        common = min(len(e), len(a))
        delta = {"missing_exact": max(0, len(e)-len(a)), "extra_exact": max(0, len(a)-len(e))}
        for dimension in dimensions:
            if absence and dimension == "role":
                # Count only paired capacity; unmatched candidates are already extra.
                matching = sum(item["role"] in ROLES.get(value, ()) for _, item in a)
            else:
                ec = Counter(item[dimension] for _, item in e)
                ac = Counter(item[dimension] for _, item in a)
                matching = sum((ec & ac).values())
            delta[dimension] = max(0, common-matching)
        if absence:
            delta["absence_value"] = max(0, common-sum(item["value"] is None for _, item in a))
        for name, count in delta.items():
            counts[name] += count
        groups.append({"expected_indices": [i for i, _ in e],
                       "actual_indices": [i for i, _ in a], "counts": delta})

    for expected_context in case.get("expected_contexts", []):
        context = expected_context["context"]
        document = case["document"]
        if document.count(context) != 1:
            counts["context"] += 1
            continue
        start = document.index(context)
        end = start + len(context)
        if not any(all(item[k] == expected_context[k] for k in ("field", "value", "role"))
                   and start <= item["span"]["start"] < item["span"]["end"] <= end for item in pool):
            counts["context"] += 1
    counts["forbidden_confirmed"] = sum(
        item["field"] in case.get("forbidden_confirmed_fields", []) and item["status"] == "confirmed"
        for item in pool)

    def safe(item, index):
        result = {"index": index}
        for dimension in DIMENSIONS:
            value = item.get(dimension)
            result[dimension] = value if type(value) is str and value in ALLOWED[dimension] else "unassessed"
        span = item.get("span", {})
        if all(type(span.get(k)) is int and span[k] >= 0 for k in ("start", "end")):
            result["span"] = {k: span[k] for k in ("start", "end")}
        return result
    return {"revision": 1, "matching": "field" if absence else "exact_value",
            "evaluated_dimensions": dimensions, "counts": counts, "groups": groups,
            "expected": [safe(item, i) for i, item in enumerate(expected)],
            "actual": [safe(item, i) for i, item in enumerate(pool)]}
