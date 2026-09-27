"""Fixed isolated source repair comparison, with no source/raw response persistence."""
import argparse, hashlib, json, time
from pathlib import Path
from .source_repair import SOURCE_REPAIR_PROMPT, repair_schema, apply_repairs
from .repair_examples import REPAIR_EXAMPLES
from .repair_value import VALUE_BOUNDARY, VALUE_BOUNDARY_V2
from .repair_state import STATE_GROUNDING, STATE_GROUNDING_V2
from .repair_units import split_repair_units
from .anchored_candidates import units
from .profile import FIELDS, validate_profile
from .solar import SolarAnalyzer, AnalysisError
from .evaluate import load_api_key
from .repair_observation import score_profile

def quote_observations(reply, field, sections):
    """Numeric diagnostics only, including when later quote validation rejects."""
    repairs=reply.get("repairs")
    patch=repairs.get(field) if type(repairs) is dict else None
    facts=patch.get("facts") if type(patch) is dict else None
    if type(facts) is not list or len(facts)>30:return []
    mapping={s.id:s.text for s in sections};result=[]
    for fact in facts:
        if type(fact) is not dict:continue
        ident=fact.get("unitId");quote=fact.get("quote");context=fact.get("context")
        text=mapping.get(ident) if type(ident) is str else None
        good_quote=type(quote) is str and 0<len(quote)<=2000
        good_context=type(context) is str and 0<len(context)<=4000
        result.append({"known_unit":text is not None,
            "quote_matches":text.count(quote) if text is not None and good_quote else None,
            "context_matches":text.count(context) if text is not None and good_context else None,
            "quote_in_context_matches":context.count(quote) if good_quote and good_context else None})
    return result

def response_format_observation(raw):
    """Return fixed shape reasons only, never provider-controlled text."""
    try:
        envelope=json.loads(raw)
        content=envelope["choices"][0]["message"]["content"]
    except (ValueError,TypeError,KeyError,IndexError,UnicodeError):
        return {"reason":"ENVELOPE_SHAPE"}
    duplicates=0
    def obj(pairs):
        nonlocal duplicates
        result={}
        for key,value in pairs:
            if key in result:duplicates+=1
            result[key]=value
        return result
    try:body=json.loads(content,object_pairs_hook=obj)
    except (ValueError,TypeError,UnicodeError):
        return {"reason":"CONTENT_JSON_INVALID"}
    if duplicates:return {"reason":"DUPLICATE_CONTENT_KEYS","duplicate_count":duplicates}
    if type(body) is not dict or set(body)!={"repairs"}:return {"reason":"ROOT_SHAPE"}
    return {"reason":"EXPECTED_SHAPE"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--value-boundary",action="store_true")
    parser.add_argument("--case-ids",nargs="+")
    parser.add_argument("--boundary-revision",choices=("v1","v2"),default="v1")
    parser.add_argument("--transfer",action="store_true")
    parser.add_argument("--state-cases",action="store_true")
    parser.add_argument("--unit-transfer",action="store_true")
    parser.add_argument("--state-grounding",action="store_true")
    parser.add_argument("--evidence-units",action="store_true")
    parser.add_argument("--effort",choices=("none","low"),default="none")
    parser.add_argument("--max-tokens",type=int,choices=(4096,8192),default=4096)
    parser.add_argument("--state-revision",choices=("v1","v2"),default="v1")
    parser.add_argument("--repeat",type=int,choices=(1,2,3),default=1)
    parser.add_argument("--interval-seconds",type=float,default=0)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live required")
    if not 0<=args.interval_seconds<=30:parser.error("interval must be between 0 and 30")
    case_file=Path(__file__).resolve().parents[2]/"specs/ai-developer/04-analysis-provider/repair-value-boundary/cases.json"
    if args.transfer:case_file=case_file.with_name("transfer-cases.json")
    if args.state_cases:
        if args.transfer:parser.error("choose one case set")
        case_file=case_file.parent.parent/"repair-state-grounding/cases.json"
    if args.unit_transfer:
        if args.transfer or args.state_cases:parser.error("choose one case set")
        case_file=case_file.parent.parent/"repair-evidence-units/transfer-cases.json"
    cases=json.loads(case_file.read_text(encoding="utf-8"))
    if args.case_ids:
        if len(set(args.case_ids))!=len(args.case_ids) or not set(args.case_ids)<=set(c["id"] for c in cases):parser.error("invalid case ids")
        cases=[c for c in cases if c["id"] in args.case_ids]
    prompt=SOURCE_REPAIR_PROMPT+REPAIR_EXAMPLES+((VALUE_BOUNDARY if args.boundary_revision=="v1" else VALUE_BOUNDARY_V2) if args.value_boundary else "")
    if args.state_grounding:prompt+=STATE_GROUNDING if args.state_revision=="v1" else STATE_GROUNDING_V2
    args.output.mkdir(parents=True,exist_ok=False)
    plan={"scope":"isolated_source_repair","model":"solar-mini4","effort":args.effort,"max_tokens":args.max_tokens,"timeout":40,
          "evidence_units":args.evidence_units,"state_revision":args.state_revision,"unit_transfer":args.unit_transfer,"state_cases":args.state_cases,"state_grounding":args.state_grounding,"value_boundary":args.value_boundary,"boundary_revision":args.boundary_revision,"transfer":args.transfer,"planned":len(cases)*args.repeat,"case_ids":[c["id"] for c in cases],"repeat":args.repeat,"interval_seconds":args.interval_seconds,
          "cases_sha256":hashlib.sha256(case_file.read_bytes()).hexdigest(),
          "prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
          "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    analyzer=SolarAnalyzer(load_api_key(),model="solar-mini4");rows=[]
    for case,iteration in ((c,i) for i in range(1,args.repeat+1) for c in cases):
        if rows and args.interval_seconds:time.sleep(args.interval_seconds)
        doc=case["document"];field=case["field"];sections=units(doc)
        if args.evidence_units:sections=split_repair_units(sections)
        previous=validate_profile(doc,case["id"],{"data":dict.fromkeys(FIELDS),"evidence":{f:[] for f in FIELDS}})
        content={"document":doc,"requestedFields":[field],"previous":previous,
                 "issues":[{"field":field,"kind":"missing","itemIndex":None,"evidenceLineIds":list(range(1,len(doc.splitlines())+1))}],
                 "units":[{"unitId":s.id,"text":s.text,"headingPath":list(s.path)} for s in sections]}
        payload={"model":"solar-mini4","messages":[{"role":"system","content":prompt},{"role":"user","content":json.dumps(content,ensure_ascii=False)}],
                 "response_format":{"type":"json_schema","json_schema":{"name":"agentfit_sections","strict":True,"schema":repair_schema([field],sections)}},
                 "reasoning_effort":args.effort,"temperature":0,"frequency_penalty":0,"max_tokens":args.max_tokens,"stream":False}
        row={"id":case["id"],"iteration":iteration,"passed":False};trace={};started=time.monotonic()
        try:
            reply,model,pt,ct=analyzer._send_payload(payload,("repairs",),_trace=trace,timeout=40)
            row["quote_observations"]=quote_observations(reply,field,sections)
            repaired=apply_repairs(doc,case["id"],previous,sections,[field],reply)
            row.update(score_profile(repaired,case["gold"]),model=model,prompt_tokens=pt,completion_tokens=ct)
            expected=case["gold"].get(field);actual=repaired["data"][field]
            # apply_repairs has validated these enums. Never persist quotations/context.
            row["fact_states"]=[{k:fact[k] for k in ("role","status","scope")} for fact in reply["repairs"][field]["facts"]]
            row["actual_state"]="unknown" if actual is None else "absent" if actual==[] else "known"
            row["selected_spans"]=[{"start":e["start"],"end":e["end"]} for e in repaired["evidence"][field]]
            if type(expected) is str:
                row["scalar_observation"]={"is_null":actual is None,"is_string":type(actual) is str,
                    "characters":len(actual) if type(actual) is str else None,
                    "contains_expected":type(actual) is str and expected in actual,
                    "prefix_characters":actual.find(expected) if type(actual) is str and expected in actual else None,
                    "suffix_characters":len(actual)-actual.find(expected)-len(expected) if type(actual) is str and expected in actual else None}
        except AnalysisError as error:
            row["error"]=error.code
            if hasattr(error,"merge_detail"):row["merge_error"]=error.merge_detail
            if error.code=="INVALID_RESPONSE":row["response_observation"]=response_format_observation(trace.get("raw"))
        finally:trace.pop("raw",None)
        row["elapsed_ms"]=round((time.monotonic()-started)*1000);rows.append(row)
        (args.output/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        print(json.dumps({k:row[k] for k in ("id","passed","elapsed_ms","error") if k in row}),flush=True)
    return 0 if all(r["passed"] for r in rows) else 1

if __name__=="__main__":raise SystemExit(main())
