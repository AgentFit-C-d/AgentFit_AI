"""Fixed isolated source repair comparison, with no source/raw response persistence."""
import argparse, hashlib, json, time
from pathlib import Path
from .source_repair import SOURCE_REPAIR_PROMPT, repair_schema, apply_repairs
from .repair_examples import REPAIR_EXAMPLES
from .repair_value import VALUE_BOUNDARY, VALUE_BOUNDARY_V2
from .anchored_candidates import units
from .profile import FIELDS, validate_profile
from .solar import SolarAnalyzer, AnalysisError
from .evaluate import load_api_key
from .repair_observation import score_profile

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--value-boundary",action="store_true")
    parser.add_argument("--case-ids",nargs="+")
    parser.add_argument("--boundary-revision",choices=("v1","v2"),default="v1")
    parser.add_argument("--transfer",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live required")
    case_file=Path(__file__).resolve().parents[2]/"specs/ai-developer/04-analysis-provider/repair-value-boundary/cases.json"
    if args.transfer:case_file=case_file.with_name("transfer-cases.json")
    cases=json.loads(case_file.read_text(encoding="utf-8"))
    if args.case_ids:
        if len(set(args.case_ids))!=len(args.case_ids) or not set(args.case_ids)<=set(c["id"] for c in cases):parser.error("invalid case ids")
        cases=[c for c in cases if c["id"] in args.case_ids]
    prompt=SOURCE_REPAIR_PROMPT+REPAIR_EXAMPLES+((VALUE_BOUNDARY if args.boundary_revision=="v1" else VALUE_BOUNDARY_V2) if args.value_boundary else "")
    args.output.mkdir(parents=True,exist_ok=False)
    plan={"scope":"isolated_source_repair","model":"solar-mini4","effort":"none","max_tokens":4096,"timeout":40,
          "value_boundary":args.value_boundary,"boundary_revision":args.boundary_revision,"transfer":args.transfer,"planned":len(cases),"case_ids":[c["id"] for c in cases],
          "cases_sha256":hashlib.sha256(case_file.read_bytes()).hexdigest(),
          "prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
          "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    analyzer=SolarAnalyzer(load_api_key(),model="solar-mini4");rows=[]
    for case in cases:
        doc=case["document"];field=case["field"];sections=units(doc)
        previous=validate_profile(doc,case["id"],{"data":dict.fromkeys(FIELDS),"evidence":{f:[] for f in FIELDS}})
        content={"document":doc,"requestedFields":[field],"previous":previous,
                 "issues":[{"field":field,"kind":"missing","itemIndex":None,"evidenceLineIds":list(range(1,len(doc.splitlines())+1))}],
                 "units":[{"unitId":s.id,"text":s.text,"headingPath":list(s.path)} for s in sections]}
        payload={"model":"solar-mini4","messages":[{"role":"system","content":prompt},{"role":"user","content":json.dumps(content,ensure_ascii=False)}],
                 "response_format":{"type":"json_schema","json_schema":{"name":"agentfit_sections","strict":True,"schema":repair_schema([field],sections)}},
                 "reasoning_effort":"none","temperature":0,"frequency_penalty":0,"max_tokens":4096,"stream":False}
        row={"id":case["id"],"passed":False};trace={};started=time.monotonic()
        try:
            reply,model,pt,ct=analyzer._send_payload(payload,("repairs",),_trace=trace,timeout=40)
            repaired=apply_repairs(doc,case["id"],previous,sections,[field],reply)
            row.update(score_profile(repaired,case["gold"]),model=model,prompt_tokens=pt,completion_tokens=ct)
            expected=case["gold"].get(field);actual=repaired["data"][field]
            if type(expected) is str:
                row["scalar_observation"]={"is_null":actual is None,"is_string":type(actual) is str,
                    "characters":len(actual) if type(actual) is str else None,
                    "contains_expected":type(actual) is str and expected in actual,
                    "prefix_characters":actual.find(expected) if type(actual) is str and expected in actual else None,
                    "suffix_characters":len(actual)-actual.find(expected)-len(expected) if type(actual) is str and expected in actual else None}
        except AnalysisError as error:row["error"]=error.code
        finally:trace.pop("raw",None)
        row["elapsed_ms"]=round((time.monotonic()-started)*1000);rows.append(row)
        (args.output/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        print(json.dumps({k:row[k] for k in ("id","passed","elapsed_ms","error") if k in row}),flush=True)
    return 0 if all(r["passed"] for r in rows) else 1

if __name__=="__main__":raise SystemExit(main())
