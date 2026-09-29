"""Conservative, opt-in candidate gate and source-free adversarial scoring."""

import re


_UNCERTAIN = re.compile(r"미정|아직|검토|제안|초안|후보|예정|가능성|논의|결정\s*전")
_OTHER_CONTEXT = re.compile(r"과거|이전|다른\s*제품|타\s*제품|경쟁사|예시|가정|시제품|실험|시험|개발")
_NEGATIVE = re.compile(r"않|없|미사용|제외|중단|금지|불가|비활성")
_POSITIVE = re.compile(r"확정|채택|도입|제공한다|사용한다|포함하기로|출시")
_ABSENT = re.compile(r"사용하지\s*않|제공하지\s*않|없다|미사용|제외하기로|도입하지\s*않")
_BOUNDARIES = ".!?。\n"
_CLAUSE_BOUNDARY = re.compile(r"[,;:，；]|(?:않|없)고\s+|하지만|그러나|반면")


def _clause_and_tail(document: str, start: int, end: int) -> tuple[str, str]:
    left = max((document.rfind(mark, 0, start) for mark in _BOUNDARIES), default=-1)
    rights = [position for mark in _BOUNDARIES
              if (position := document.find(mark, end)) >= 0]
    right = min(rights) + 1 if rights else len(document)
    sentence = document[left + 1:right]
    relative_start, relative_end = start - left - 1, end - left - 1
    clause_start, clause_end = 0, len(sentence)
    for boundary in _CLAUSE_BOUNDARY.finditer(sentence):
        if boundary.end() <= relative_start:
            clause_start = boundary.end()
        elif boundary.start() >= relative_end:
            clause_end = boundary.start()
            break
        else:
            return "", ""
    return sentence[clause_start:clause_end].strip(), sentence[relative_end:clause_end]


def _conflicting_mentions(document: str, quote: str) -> bool:
    statements = [part.strip() for part in re.split(r"[.!?。\n]+", document)
                  if quote in part and not _UNCERTAIN.search(part)
                  and not _OTHER_CONTEXT.search(part)]
    has_present = any(_POSITIVE.search(part) and not _NEGATIVE.search(part)
                      for part in statements)
    has_absent = any(_ABSENT.search(part) for part in statements)
    return has_present and has_absent


def guard_candidate(document: str, *, field: str, state: str,
                    start: int, end: int) -> str:
    """Return only allow/review. Review means no automatic confirmation."""
    if (type(document) is not str or not document.strip() or
            type(field) is not str or not field or
            state not in ("present", "absent") or
            type(start) is not int or type(end) is not int or
            not 0 <= start < end <= len(document)):
        raise ValueError("invalid candidate")
    clause, tail = _clause_and_tail(document, start, end)
    if not clause or _UNCERTAIN.search(clause) or _OTHER_CONTEXT.search(clause):
        return "review"
    if _conflicting_mentions(document, document[start:end]):
        return "review"
    if state == "present":
        return "review" if _NEGATIVE.search(clause) or not _POSITIVE.search(tail) else "allow"
    return "allow" if _ABSENT.search(tail) else "review"


def evaluate_cases(cases: list[dict], decisions: dict[str, str]) -> dict:
    """Score all fixed cases; never copy a source document into the result."""
    if (type(cases) is not list or type(decisions) is not dict or
            any(type(case) is not dict or type(case.get("id")) is not str or
                case.get("expected_decision") not in ("allow", "review") or
                case.get("category") not in ("repeat", "negation", "proposal")
                for case in cases)):
        raise ValueError("invalid evaluation cases")
    ids = [case["id"] for case in cases]
    if (len(set(ids)) != len(ids) or set(decisions) != set(ids) or
            any(decision not in ("allow", "review") for decision in decisions.values())):
        raise ValueError("incomplete evaluation")
    by_category = {}
    for category in ("repeat", "negation", "proposal"):
        group = [case for case in cases if case["category"] == category]
        by_category[category] = {
            "total": len(group),
            "false_auto_confirmations": sum(
                decisions[case["id"]] == "allow" and case["expected_decision"] == "review"
                for case in group),
            "missed_allows": sum(
                decisions[case["id"]] == "review" and case["expected_decision"] == "allow"
                for case in group),
        }
    return {"total": len(cases),
            "false_auto_confirmations": sum(item["false_auto_confirmations"]
                                            for item in by_category.values()),
            "missed_allows": sum(item["missed_allows"]
                                 for item in by_category.values()),
            "by_category": by_category}
