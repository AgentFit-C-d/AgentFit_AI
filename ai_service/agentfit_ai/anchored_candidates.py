"""Source-anchored candidates without model-generated classification at extraction."""
from .sections import split_sections, Section
from .solar import AnalysisError, _object
from .evidence import resolve_quote, EvidenceError
from .section_analysis import merge_profile, SCOPES, EXCLUSIONS
from .field_role_schema import compatible, constrain_schema
from .profile import FIELDS

def units(document):
    return [Section("U"+str(i+1).zfill(4),s.start,s.end,s.path,s.text)
            for i,s in enumerate(split_sections(document,preserve_blocks=True))]

def candidate_schema(batch):
    return _object({"units":{"type":"array","minItems":len(batch),"maxItems":len(batch),
        "items":_object({"unitId":{"type":"string","enum":[s.id for s in batch]},
        "quotes":{"type":"array","maxItems":30,"items":{"type":"string","minLength":1,"maxLength":2000}}})}})

def validate_quotes(reply,batch,start_index,*,expand_occurrences=False):
    def fail():raise AnalysisError("ANCHORED_CANDIDATE")
    if type(reply) is not dict or set(reply)!={"units"} or type(reply["units"]) is not list:fail()
    groups=reply["units"]
    if any(type(g) is not dict or set(g)!={"unitId","quotes"} or type(g["unitId"]) is not str for g in groups):fail()
    ids=[g["unitId"] for g in groups]
    if len(set(ids))!=len(ids) or set(ids)!={s.id for s in batch}:fail()
    mapping={g["unitId"]:g["quotes"] for g in groups};result=[]
    for unit in batch:
        quotes=mapping[unit.id]
        if type(quotes) is not list or len(quotes)>30 or any(type(q) is not str for q in quotes):fail()
        if len(set(quotes))!=len(quotes):fail()
        for quote in quotes:
            if expand_occurrences:
                if not quote.strip() or len(quote)>2000:fail()
                position=unit.text.find(quote)
                if position<0:fail()
                while position>=0:
                    if start_index+len(result)>=120:raise AnalysisError("SECTION_LIMIT")
                    result.append({"unitId":unit.id,"quote":quote,
                        "span":{"start":unit.start+position,"end":unit.start+position+len(quote)}})
                    position=unit.text.find(quote,position+1)
            else:
                try:span=resolve_quote(unit.text,quote,None)
                except EvidenceError:fail()
                result.append({"id":"F"+str(start_index+len(result)+1).zfill(4),"unitId":unit.id,
                    "quote":quote,"span":{"start":unit.start+span["start"],"end":unit.start+span["end"]}})
    if expand_occurrences:
        result.sort(key=lambda x:(x["span"]["start"],x["span"]["end"],x["quote"]))
        for index,item in enumerate(result,start_index+1):item["id"]="F"+str(index).zfill(4)
    if start_index+len(result)>120:raise AnalysisError("SECTION_LIMIT")
    return result

def judgment_schema(pool,*,selected_constraints=False):
    # Reuse field-role branches; replace quotation properties with a decision.
    from .section_analysis import extraction_schema
    sample=Section("U0001",0,1,(),"x")
    source=constrain_schema(extraction_schema([sample],quote_only=True))
    branches=source["properties"]["sections"]["items"]["properties"]["facts"]["items"]["anyOf"]
    for branch in branches:
        props=branch["properties"]
        for name in ("quote","context"):
            del props[name]
        props["decision"]={"type":"string","enum":["selected",*EXCLUSIONS]}
        branch["required"]=list(props)
    if selected_constraints:
        from copy import deepcopy
        from .evidence import ROLES
        selected=[]
        for branch in branches:
            props=branch["properties"]
            props["decision"]["enum"]=list(EXCLUSIONS)
            eligible=deepcopy(branch)
            field=props["field"]["enum"][0]
            chosen=eligible["properties"]
            chosen["role"]["enum"]=list(ROLES[field])
            chosen["status"]["enum"]=[s for s in props["status"]["enum"] if s in ("confirmed","absent")]
            chosen["scope"]["enum"]=["current"]
            chosen["decision"]["enum"]=["selected"]
            selected.append(eligible)
        branches.extend(selected)
    branches.append(_object({"decision":{"type":"string","enum":["irrelevant"]}}))
    return _object({"decisions":_object({item["id"]:{"anyOf":branches} for item in pool})})

def classify(reply,pool,document,document_id):
    def fail():raise AnalysisError("ANCHORED_JUDGMENT")
    if type(reply) is not dict or set(reply)!={"decisions"} or type(reply["decisions"]) is not dict:fail()
    decisions=reply["decisions"]
    if set(decisions)!={x["id"] for x in pool}:fail()
    classified=[];selected={}
    for source in pool:
        item=decisions[source["id"]]
        if type(item) is not dict:fail()
        if item=={"decision":"irrelevant"}:continue
        if set(item)!={"field","role","status","scope","decision"} or any(type(v) is not str for v in item.values()):fail()
        if not compatible(item["field"],item["role"],item["status"]) or item["scope"] not in SCOPES or item["decision"] not in ("selected",*EXCLUSIONS):fail()
        value=None if item["status"]=="absent" else source["quote"]
        if value is not None and len(value)>200:fail()
        classified.append({**source,**{k:item[k] for k in ("field","role","status","scope")},"value":value})
        selected[source["id"]]=item["decision"]
    return merge_profile(document,document_id,{"decisions":selected},classified)
