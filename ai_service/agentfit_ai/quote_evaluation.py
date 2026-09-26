"""Fixed short-section gate for quote-only extraction; no full-document evaluation."""
import argparse
from collections import Counter
import hashlib
import json
import time
from pathlib import Path
from .evaluate import load_api_key
from .section_analysis import SectionAnalyzer, QUOTE_EXTRACT_PROMPT, extraction_schema, validate_candidates
from .sections import split_sections
from .solar import AnalysisError
from .evidence import ROLES

CASES=Path(__file__).resolve().parents[1]/"tests/fixtures/quote-extraction-cases.json"


def score(pool,case):
    for expected in case.get("expected_contexts",[]):
        context=expected["context"]
        if case["document"].count(context)!=1:return False
        start=case["document"].index(context)
        end=start+len(context)
        if not any(x["field"]==expected["field"] and x["value"]==expected["value"]
                   and x["role"]==expected["role"] and start<=x["span"]["start"]<x["span"]["end"]<=end for x in pool):
            return False
    if "expected" in case:
        actual=[(x["field"],x["value"],x["role"],x["status"],x["scope"]) for x in pool]
        return Counter(actual)==Counter(tuple(x) for x in case["expected"])
    if "expected_absent" in case:
        return len(pool)==len(case["expected_absent"]) and {x["field"] for x in pool}==set(case["expected_absent"]) and all(x["status"]=="absent" and x["value"] is None and x["scope"]=="current" and x["role"] in ROLES[x["field"]] for x in pool)
    expected=case["expected_roles"]
    return (len(pool)==len(expected) and all(x["value"] in expected and x["role"]==expected[x["value"]] for x in pool)
            and not any(x["field"] in case["forbidden_confirmed_fields"] and x["status"]=="confirmed" for x in pool))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live is required")
    cases=json.loads(CASES.read_text(encoding="utf-8"))
    analyzer=SectionAnalyzer(load_api_key(),model="solar-mini4",quote_only=True,jev_merge=True)
    args.output.mkdir(parents=True,exist_ok=False)
    plan={"model":"solar-mini4","version":"section-quotes-v3","scoring_revision":2,"planned":len(cases),
          "cases_sha256":hashlib.sha256(CASES.read_bytes()).hexdigest(),
          "prompt_sha256":hashlib.sha256(QUOTE_EXTRACT_PROMPT.encode()).hexdigest(),
          "gate":"all 6 structurally valid and exact criteria passed","max_tokens":4096,
          "reasoning_effort":"none","temperature":0,"timeout":40}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    rows=[]
    with (args.output/"attempts.jsonl").open("x",encoding="utf-8") as log:
        for case in cases:
            sections=split_sections(case["document"])
            content={"document_context":{"headings":[list(s.path) for s in sections],"opening":sections[0].text},
                     "sections":[{"sectionId":s.id,"headingPath":list(s.path),"text":s.text} for s in sections]}
            schema=extraction_schema(sections,quote_only=True)
            payload={"model":"solar-mini4","messages":[{"role":"system","content":QUOTE_EXTRACT_PROMPT},
                     {"role":"user","content":json.dumps(content,ensure_ascii=False)}],
                     "response_format":{"type":"json_schema","json_schema":{"name":"agentfit_sections","strict":True,"schema":schema}},
                     "reasoning_effort":"none","frequency_penalty":0,"temperature":0,"max_tokens":4096,"stream":False}
            row={"id":case["id"]};started=time.monotonic();trace={}
            try:
                reply=analyzer._send_payload(payload,("sections",),_trace=trace,timeout=40)
                pool=validate_candidates(reply[0],sections,0,quote_only=True)
                row.update(structural=True,passed=score(pool,case),candidate_count=len(pool),
                           model=reply[1],prompt_tokens=reply[2],completion_tokens=reply[3])
            except AnalysisError as error:
                row.update(structural=False,passed=False,error=error.code,
                           detail=getattr(error,"candidate_detail",None))
            row["elapsed_ms"]=round((time.monotonic()-started)*1000)
            trace.clear()  # This standalone gate stores no raw response or Profile.
            rows.append(row);log.write(json.dumps(row)+"\n");log.flush()
            print(json.dumps(row),flush=True)
    report=dict(plan,results=rows,passed=sum(r["passed"] for r in rows),
                structural=sum(r["structural"] for r in rows))
    report["gate_passed"]=report["passed"]==6 and len(rows)==6
    (args.output/"results.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("passed","structural","gate_passed")}))
    return 0 if report["gate_passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
