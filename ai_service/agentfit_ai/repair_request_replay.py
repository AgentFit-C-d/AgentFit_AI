"""Synthetic-only request capture/replay; never imported by the service."""
import argparse
import copy
import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch
from .anchored_analysis import AnchoredAnalyzer
from .anchored_candidates import units
from .evaluate import load_api_key
from .profile import FIELDS, validate_profile
from .repair_observation import observe_run, score_profile
from .repair_examples import REPAIR_EXAMPLES
from .repair_value import VALUE_BOUNDARY_V2
from .repair_state import STATE_GROUNDING_V2
from .source_repair import SOURCE_REPAIR_PROMPT, repair_schema, apply_repairs
from .solar import AnalysisError

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--replay-model",choices=("solar-mini4","solar-pro4"))
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live required")
    repo=Path(__file__).resolve().parents[2]
    cases=json.loads((repo/"specs/ai-developer/04-analysis-provider/anchored-prompt-contract/new-cases.json").read_text(encoding="utf-8"))
    case=next(c for c in cases if c["id"]=="N-004")
    doc=case["document"];sections=units(doc)
    args.output.mkdir(parents=True,exist_ok=False)
    plan={"scope":"synthetic_actual_request_replay","case_id":case["id"],"case_sha256":digest(case),
          "model":"solar-mini4","replay_model":args.replay_model or "solar-mini4","max_tokens":4096,"effort":"low","replay_count":3,
          "replay_timeout":40,"interval_seconds":2,"full_flow_limit_seconds":60,"full_flow_limit_calls":6,
          "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    analyzer=AnchoredAnalyzer(load_api_key(),model="solar-mini4",prompt_revision="v2",
        source_repair=True,review_effort="low",repair_examples=True,review_examples=True,
        review_expression=True,repair_value_boundary=True,repair_state_grounding=True,repair_effort="low")
    captured=[];captured_timeouts=[]
    send=analyzer._send_payload
    def capture(payload,names,**kwargs):
        if tuple(names)==("repairs",):
            captured.append(copy.deepcopy(payload))
            captured_timeouts.append(float(kwargs["timeout"]))
        return send(payload,names,**kwargs)
    with patch.object(analyzer,"_send_payload",side_effect=capture):
        full=observe_run(analyzer,doc,case["id"],case["gold"])
    report={"full_flow":full,"captured_count":len(captured),"original_request_timeouts":captured_timeouts,"replay_timeout":40,"replays":[]}
    def save():
        (args.output/"results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    print(json.dumps({"full_passed":full["passed"],"error":full.get("error"),"captured_count":len(captured)}),flush=True)
    if len(captured)!=1:return 1
    payload=captured[0];content=json.loads(payload["messages"][1]["content"])
    previous=validate_profile(doc,case["id"],{"data":dict.fromkeys(FIELDS),"evidence":{f:[] for f in FIELDS}})
    expected={"document":doc,"requestedFields":["ai"],"previous":previous,
        "issues":[{"field":"ai","kind":"missing","itemIndex":None,"evidenceLineIds":list(range(1,len(doc.splitlines())+1))}],
        "units":[{"unitId":s.id,"text":s.text,"headingPath":list(s.path)} for s in sections]}
    report["comparison"]={k:content.get(k)==v for k,v in expected.items()}
    report["comparison"]["system_prompt"]=payload["messages"][0]["content"]==SOURCE_REPAIR_PROMPT+REPAIR_EXAMPLES+VALUE_BOUNDARY_V2+STATE_GROUNDING_V2
    report["comparison"]["schema"]=payload["response_format"]["json_schema"]["schema"]==repair_schema(["ai"],sections)
    report["original_request_sha256"]=digest(payload)
    if args.replay_model:payload["model"]=args.replay_model
    report["request_sha256"]=digest(payload)
    save()
    print(json.dumps({"comparison":report["comparison"]}),flush=True)
    for iteration in range(1,4):
        time.sleep(2)
        trace={};started=time.monotonic();row={"iteration":iteration,"passed":False}
        try:
            reply,model,pt,ct=send(copy.deepcopy(payload),("repairs",),_trace=trace,timeout=40)
            result=apply_repairs(doc,case["id"],content["previous"],sections,content["requestedFields"],reply)
            row.update(score_profile(result,case["gold"]),model=model,prompt_tokens=pt,completion_tokens=ct)
        except AnalysisError as error:row["error"]=error.code
        finally:
            trace.pop("raw",None)
            row["transport"]={k:trace[k] for k in ("prompt_tokens","completion_tokens","max_tokens","provider_elapsed_ms") if type(trace.get(k)) in (int,float)}
        row["elapsed_ms"]=round((time.monotonic()-started)*1000)
        row["request_unchanged"]=digest(payload)==report["request_sha256"]
        report["replays"].append(row);save()
        print(json.dumps({k:row[k] for k in ("iteration","passed","error","elapsed_ms") if k in row}),flush=True)
    return 0 if full["passed"] and all(r["passed"] for r in report["replays"]) else 1

if __name__=="__main__":raise SystemExit(main())
