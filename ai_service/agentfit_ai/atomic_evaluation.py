"""Paired fixed-candidate tuning evaluation; no raw model output persistence."""
import argparse, hashlib, json, time
from pathlib import Path
from .atomic_verdict import ATOMIC_PROMPT, atomic_schema, classify_atomic, validate_verdicts
from .anchored_candidates import judgment_schema, classify
from .candidate_occurrences import candidate_views, JUDGMENT_FOCUS_PROMPT
from .candidate_occurrence_evaluation import fixed_pool, score_alternatives
from .repair_observation import score_profile
from .anchored_evaluation import safe_diagnostics
from .profile import FIELDS
from .solar import SolarAnalyzer, AnalysisError
from .evaluate import load_api_key

def conflict_recognized(reply,pool,case,atomic):
    expected=case["expected_conflict_decisions"]
    if atomic:
        values=validate_verdicts(reply,pool)
        return all(values.get(ident)=="conflict" for ident in expected) and all(
            value=="omit" for ident,value in values.items() if ident not in expected)
    classify(reply,pool,case["document"],case["id"])
    values=reply["decisions"]
    return all(values.get(ident)==fact for ident,fact in expected.items()) and all(
        value=={"decision":"irrelevant"} for ident,value in values.items() if ident not in expected)

def false_confirmations(profile,case):
    """Wrong facts or unsupported positions; pure omissions are scored separately."""
    scores=score_profile(profile,case["gold"])["fields"]
    wrong=[]
    for field in FIELDS:
        actual=profile["data"][field];expected=case["gold"].get(field)
        if actual is None:continue
        if expected is None:
            wrong.append(field);continue
        if expected==[] or type(expected) is str:
            wrong_value=actual!=expected
        else:
            wrong_value=actual==[] or type(actual) is not list or len(actual)>scores[field]["exact_groups"]
        spans={(s["start"],s["end"]) for s in profile["evidence"][field]}
        supported=any(spans<={(s["start"],s["end"]) for s in alt.get(field,[])}
                      for alt in case["accepted_evidence_sets"])
        if wrong_value or not supported:wrong.append(field)
    return wrong

def evaluate_case(analyzer,case,atomic):
    sections,pool=fixed_pool(case)
    schema=atomic_schema(pool) if atomic else judgment_schema(pool,selected_constraints=True)
    content={"document":case["document"],"candidates":candidate_views(pool,sections,focus=True)}
    payload={"model":"solar-pro4","messages":[{"role":"system","content":ATOMIC_PROMPT if atomic else JUDGMENT_FOCUS_PROMPT},
        {"role":"user","content":json.dumps(content,ensure_ascii=False)}],
        "response_format":{"type":"json_schema","json_schema":{"name":"agentfit_sections","strict":True,"schema":schema}},
        "reasoning_effort":"none","temperature":0,"frequency_penalty":0,"max_tokens":4096,"stream":False}
    row={"id":case["id"],"arm":"atomic" if atomic else "baseline","passed":False,
         "provider_calls":1,"candidate_count":len(pool),"profile_returned":False}
    trace={};started=time.monotonic()
    try:
        reply,model,pt,ct=analyzer._send_payload(payload,("decisions",),_trace=trace,timeout=40)
        row.update(prompt_tokens=pt,completion_tokens=ct,model=model)
        if case.get("expected_kind")=="conflict":
            recognized=conflict_recognized(reply,pool,case,atomic)
            row.update(result_kind="conflict",conflict_recognized=recognized,passed=recognized)
        else:
            profile=(classify_atomic if atomic else classify)(reply,pool,case["document"],case["id"])
            row.update(score_profile(profile,case["gold"]),**score_alternatives(profile,case["accepted_evidence_sets"]))
            row["passed"]=row["passed"] and row["evidence_matched"]
            row.update(result_kind="profile",profile_returned=True,false_confirmation_fields=false_confirmations(profile,case))
            row["selected_spans"]={f:[{"start":s["start"],"end":s["end"]} for s in profile["evidence"][f]]
                                   for f in FIELDS if profile["evidence"][f]}
    except AnalysisError as error:
        row["error"]=error.code
        call={"call":1,"stage":"judgment","error":error.code}
        if hasattr(error,"merge_detail"):call["merge_error"]=error.merge_detail
        row.update(safe_diagnostics({"calls":[call]}))
    finally:
        trace.pop("raw",None)
        for key in ("prompt_tokens","completion_tokens","request_bytes","response_bytes","provider_elapsed_ms"):
            value=trace.get(key)
            if type(value) is int and value>=0:row[key]=value
        row["elapsed_ms"]=round((time.monotonic()-started)*1000)
    return row

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live required")
    root=Path(__file__).resolve().parents[2]/"specs/ai-developer/04-analysis-provider"
    case_path=root/"candidate-occurrence-expansion/evaluation-cases.json"
    extra_path=root/"atomic-candidate-verdict/counterexamples.json"
    gold_path=root/"atomic-candidate-verdict/conflict-gold.json"
    dataset=json.loads(case_path.read_text(encoding="utf-8"))
    extra=json.loads(extra_path.read_text(encoding="utf-8"))
    conflict_gold=json.loads(gold_path.read_text(encoding="utf-8"))
    if hashlib.sha256(case_path.read_bytes()).hexdigest()!=extra["existing27_sha256"]:
        raise ValueError("frozen case hash mismatch")
    for name,digest in dataset["source_hashes"].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError("source hash mismatch")
    cases=dataset["cases"]+extra["cases"]
    for case in cases:
        fixed_pool(case)
        if case.get("expected_kind")=="conflict":
            case["expected_conflict_decisions"]=conflict_gold[case["id"]]
    key=load_api_key()
    args.output.mkdir(parents=True,exist_ok=False)
    plan={"scope":"paired_fixed_candidates","model":"solar-pro4","reasoning_effort":"none",
          "max_tokens":4096,"timeout":40,"interval_seconds":2,"planned_cases":len(cases),"planned_calls":2*len(cases),
          "order":"zero-based even: baseline first; odd: atomic first","held_out":False,
          "case_hashes":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (case_path,extra_path,gold_path)},
          "source_hashes":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")},
          "prompt_hashes":{"baseline":hashlib.sha256(JUDGMENT_FOCUS_PROMPT.encode()).hexdigest(),
                           "atomic":hashlib.sha256(ATOMIC_PROMPT.encode()).hexdigest()}}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    analyzer=SolarAnalyzer(key,model="solar-pro4");rows=[]
    for index,case in enumerate(cases):
        for atomic in ((False,True) if index%2==0 else (True,False)):
            if rows:time.sleep(2)
            row=evaluate_case(analyzer,case,atomic);rows.append(row)
            (args.output/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
            print(json.dumps({k:row[k] for k in ("id","arm","passed","error","elapsed_ms") if k in row}),flush=True)
    return 0 if all(row["passed"] for row in rows) else 1

if __name__=="__main__":raise SystemExit(main())
