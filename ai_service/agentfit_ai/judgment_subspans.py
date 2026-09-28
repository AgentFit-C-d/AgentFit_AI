"""Opt-in judgments anchored to exact subspans of source candidates."""

from copy import deepcopy

from .anchored_candidates import judgment_schema
from .candidate_occurrences import JUDGMENT_FOCUS_PROMPT
from .field_role_schema import compatible
from .profile import FIELDS
from .section_analysis import EXCLUSIONS, SCOPES, merge_profile
from .solar import AnalysisError, _object


SUBSPAN_PROMPT = (JUDGMENT_FOCUS_PROMPT
    .replace(
        '각 값은 {"decision":"irrelevant"} 또는 field,role,status,scope,decision의 5개 키를 모두 가진 객체다.',
        '각 값은 {"facts":[]}이며 각 fact는 quote,field,role,status,scope,decision의 6개 키를 가진다. 후보 하나에서 독립 사실을 최대 5개까지 분리한다.')
    .replace('후보 인용은 바꾸거나 추가할 수 없다. ID를 빠뜨리지 않는다.',
             'fact.quote는 해당 후보 인용 안의 정확한 연속 부분 문자열이어야 한다. 다른 후보의 문구를 가져오거나 새 문구를 만들지 않는다. 모든 ID를 포함한다.')
    .replace('decision=irrelevant로 제외해도 된다.', 'facts=[]로 제외한다.')
    .replace('또는 단독 irrelevant.', '. 무관한 후보는 facts=[]로 제외한다.'))


def subspan_schema(pool):
    sample = judgment_schema([{"id": "F0001"}], selected_constraints=True)
    branches = [deepcopy(branch) for branch in sample["properties"]["decisions"]
                ["properties"]["F0001"]["anyOf"]
                if "field" in branch["properties"]]
    for branch in branches:
        branch["properties"]["quote"] = {"type": "string", "minLength": 1,
                                          "maxLength": 2000}
        branch["required"].append("quote")
    fact = {"anyOf": branches}
    return _object({"decisions": _object({source["id"]: _object({
        "facts": {"type": "array", "maxItems": 5, "items": fact}})
        for source in pool})})


def classify_subspans(reply, pool, document, document_id):
    def fail():
        raise AnalysisError("ANCHORED_JUDGMENT")

    if (type(reply) is not dict or set(reply) != {"decisions"} or
            type(reply["decisions"]) is not dict or
            set(reply["decisions"]) != {source["id"] for source in pool}):
        fail()
    derived = []
    selected = {}
    for source in pool:
        group = reply["decisions"][source["id"]]
        if type(group) is not dict or set(group) != {"facts"} or type(group["facts"]) is not list or len(group["facts"]) > 5:
            fail()
        occupied = []
        for index, fact in enumerate(group["facts"], 1):
            if (type(fact) is not dict or set(fact) != {
                    "quote", "field", "role", "status", "scope", "decision"} or
                    any(type(value) is not str for value in fact.values())):
                fail()
            quote = fact["quote"]
            if (not quote.strip() or source["quote"].count(quote) != 1 or
                    (fact["status"] != "absent" and len(quote) > 200) or
                    fact["field"] not in FIELDS or
                    not compatible(fact["field"], fact["role"], fact["status"]) or
                    fact["scope"] not in SCOPES or
                    fact["decision"] not in ("selected", *EXCLUSIONS)):
                fail()
            start = source["span"]["start"] + source["quote"].index(quote)
            end = start + len(quote)
            if document[start:end] != quote or any(start < stop and end > begin
                                                    for begin, stop in occupied):
                fail()
            occupied.append((start, end))
            candidate_id = source["id"] + ":" + str(index)
            derived.append({"id": candidate_id, "unitId": source["unitId"],
                            "quote": quote, "span": {"start": start, "end": end},
                            **{key: fact[key] for key in ("field", "role", "status", "scope")},
                            "value": None if fact["status"] == "absent" else quote})
            selected[candidate_id] = fact["decision"]
            if len(derived) > 120:
                raise AnalysisError("SECTION_LIMIT")
    return merge_profile(document, document_id, {"decisions": selected}, derived)
