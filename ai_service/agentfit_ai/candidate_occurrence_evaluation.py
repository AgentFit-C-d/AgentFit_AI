"""Frozen tuning comparison; never persist source, model text, or secrets."""
import argparse, hashlib, json, time
from pathlib import Path
from .anchored_candidates import units, validate_quotes, judgment_schema, classify
from .anchored_prompts import JUDGMENT_PROMPT_V2
from .candidate_occurrences import candidate_views, JUDGMENT_FOCUS_PROMPT
from .anchored_analysis import AnchoredAnalyzer
from .anchored_evaluation import safe_diagnostics
from .solar import SolarAnalyzer, AnalysisError
from .evaluate import load_api_key
from .repair_observation import score_profile
from .value_repair_evaluation import score_evidence
from .profile import FIELDS

def score_alternatives(profile, alternatives):
    scores=[score_evidence(profile,expected) for expected in alternatives]
    matched=next((i for i,s in enumerate(scores) if s["evidence_matched"]),None)
    return {"evidence_matched":matched is not None,"evidence_alternative":matched,
            "evidence_mismatch_fields":[] if matched is not None else
                min((s["evidence_mismatch_fields"] for s in scores),key=len,default=list(FIELDS))}

def error_diagnostics(error):
    return safe_diagnostics(getattr(error,"diagnostics",None) or {})

def fixed_pool(case):
    sections=units(case["document"])
    pool=validate_quotes(case["fixed_extraction_reply"],sections,0,expand_occurrences=True)
    actual=[{"unitId":p["unitId"],"quote":p["quote"],**p["span"]} for p in pool]
    if actual!=case["expected_occurrences"]:
        raise ValueError("frozen occurrence reference mismatch: "+case["id"])
    return sections,pool

def judge(analyzer,case,focus):
    sections,pool=fixed_pool(case)
    prompt=JUDGMENT_FOCUS_PROMPT if focus else JUDGMENT_PROMPT_V2
    content={"document":case["document"],"candidates":candidate_views(pool,sections,focus=focus)}
    payload={"model":"solar-pro4","messages":[{"role":"system","content":prompt},
             {"role":"user","content":json.dumps(content,ensure_ascii=False)}],
             "response_format":{"type":"json_schema","json_schema":{"name":"agentfit_sections",
               "strict":True,"schema":judgment_schema(pool)}},
             "reasoning_effort":"none","temperature":0,"frequency_penalty":0,"max_tokens":4096,"stream":False}
    trace={}
    call={"call":1,"stage":"judgment","outcome":"started","reasoning_effort":"none","max_tokens":4096}
    try:
        reply,model,pt,ct=analyzer._send_payload(payload,("decisions",),_trace=trace,timeout=40)
        call.update(outcome="response_received",prompt_tokens=pt,completion_tokens=ct)
        profile=classify(reply,pool,case["document"],case["id"])
        return profile,{"provider_calls":1,"candidate_count":len(pool),"prompt_tokens":pt,"completion_tokens":ct}
    except AnalysisError as error:
        call.update(outcome="validation_failed" if call["outcome"]=="response_received" else "failed",error=error.code)
        error.diagnostics={"calls":[call],"candidate_count":len(pool)}
        raise
    finally:trace.pop("raw",None)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--mode",choices=("judgment","full"),required=True)
    parser.add_argument("--focus",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live required")
    root=Path(__file__).resolve().parents[2]
    case_file=root/"specs/ai-developer/04-analysis-provider/candidate-occurrence-expansion/evaluation-cases.json"
    dataset=json.loads(case_file.read_text(encoding="utf-8"))
    cases=dataset["cases"]
    for case in cases:fixed_pool(case)
    for name,digest in dataset["source_hashes"].items():
        if hashlib.sha256((case_file.parent.parent/name).read_bytes()).hexdigest()!=digest:
            raise ValueError("source hash mismatch: "+name)
    key=load_api_key()
    args.output.mkdir(parents=True,exist_ok=False)
    config=dict(model="solar-pro4",prompt_revision="v2",review_effort="low",source_repair=True,
        repair_examples=True,review_examples=True,review_expression=True,repair_value_boundary=True,
        repair_state_grounding=True,repair_effort="none",candidate_occurrences=args.focus)
    plan={"scope":"isolated_judgment" if args.mode=="judgment" else "full_flow",
        "focus":args.focus,"planned":len(cases),"interval_seconds":2,"model":"solar-pro4",
        "judgment_effort":"none","max_tokens":4096,"judgment_timeout":40,
        "full_flow_config":config if args.mode=="full" else None,
        "cases_sha256":hashlib.sha256(case_file.read_bytes()).hexdigest(),
        "source_hashes":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            Path(__file__).parent.glob("*.py")}}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    analyzer=SolarAnalyzer(key,model="solar-pro4") if args.mode=="judgment" else AnchoredAnalyzer(key,**config)
    rows=[]
    for case in cases:
        if rows:time.sleep(2)
        row={"id":case["id"],"passed":False};started=time.monotonic()
        try:
            if args.mode=="judgment":
                profile,diagnostic=judge(analyzer,case,args.focus)
                row.update(diagnostic)
            else:
                result=analyzer.analyze(case["document"],case["id"])
                profile=result.profile
                row.update(safe_diagnostics(result.diagnostics),provider_calls=result.provider_calls,
                    first_pass=result.first_pass_validated)
                count=result.diagnostics.get("candidate_count")
                if type(count) is int:row["candidate_count"]=count
            row.update(score_profile(profile,case["gold"]),
                **score_alternatives(profile,case["accepted_evidence_sets"]))
            row["passed"]=row["passed"] and row["evidence_matched"]
            row["selected_spans"]={f:[{"start":s["start"],"end":s["end"]} for s in profile["evidence"][f]]
                for f in FIELDS if profile["evidence"][f]}
        except AnalysisError as error:
            row["error"]=error.code
            row.update(error_diagnostics(error))
            diagnostic=getattr(error,"diagnostics",None) or {}
            if type(diagnostic.get("candidate_count")) is int:row["candidate_count"]=diagnostic["candidate_count"]
            row["provider_calls"]=len(diagnostic.get("calls",[]))
        row["elapsed_ms"]=round((time.monotonic()-started)*1000)
        rows.append(row)
        (args.output/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        print(json.dumps({k:row[k] for k in ("id","passed","error","elapsed_ms") if k in row}),flush=True)
    return 0 if all(r["passed"] for r in rows) else 1

if __name__=="__main__":raise SystemExit(main())
