"""Fixed paired semantic-review diagnostic, independent of extraction and repair."""
from collections import Counter

def assess_review(issues, expected):
    def signature(issue):
        return (issue["field"],issue["kind"],issue["itemIndex"],tuple(sorted(issue["evidenceLineIds"])))
    def semantic_signature(issue):
        return (issue["field"],issue["kind"],issue["itemIndex"],tuple(sorted(set(issue["evidenceLineIds"]))))
    return {"matched":Counter(map(semantic_signature,issues))==Counter(map(semantic_signature,expected)),
            "exact_match":Counter(map(signature,issues))==Counter(map(signature,expected)),
            "false_acceptance":bool(expected) and not issues,
            "false_rejection":not expected and bool(issues)}

def cases():
    import json
    from pathlib import Path
    from .profile import FIELDS,validate_profile
    repo=Path(__file__).resolve().parents[2]
    base=json.loads((repo/"ai_service/tests/fixtures/quote-extraction-cases.json").read_text(encoding="utf-8"))
    extra=json.loads((repo/"specs/ai-developer/04-analysis-provider/anchored-prompt-contract/new-cases.json").read_text(encoding="utf-8"))
    by_id={c["id"]:c["document"] for c in base+extra}
    values={"Q-001":("features",["장소 확인","후보 선택"]),
            "Q-002":("features",["회원 승인을 요청한다","회원 승인을 처리한다"]),
            "Q-004":("external_integrations",[]),"N-004":("ai",["Lyra"])}
    result=[]
    for ident,(field,items) in values.items():
        document=by_id[ident]
        for state in ("correct","missing"):
            data=dict.fromkeys(FIELDS);evidence={f:[] for f in FIELDS};expected=[]
            if state=="correct":
                data[field]=items
                quotes=items or [document]
                for quote in quotes:
                    assert document.count(quote)==1
                    start=document.index(quote)
                    evidence[field].append({"start":start,"end":start+len(quote)})
            else:expected=[{"field":field,"kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
            profile=validate_profile(document,ident,{"data":data,"evidence":evidence})
            result.append({"id":ident+"-"+state,"document":document,"profile":profile,"expected":expected})
    return result

def main():
    import argparse,json,hashlib,time
    from pathlib import Path
    from .solar import SolarAnalyzer,AnalysisError
    from .semantic_review import REVIEW_PROMPT,validate_review,ReviewValidationError
    from .evaluate import load_api_key
    from .review_examples import REVIEW_EXAMPLES
    parser=argparse.ArgumentParser(description="Eight paired review probes; not a readiness gate.")
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--contract-examples",action="store_true")
    parser.add_argument("--effort",choices=("none","low"),required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live required")
    samples=cases()
    prompt=REVIEW_PROMPT+(REVIEW_EXAMPLES if args.contract_examples else "")
    args.output.mkdir(parents=True,exist_ok=False)
    plan={"scope":"paired_review_only","scoring_revision":2,"planned":len(samples),"effort":args.effort,"contract_examples":args.contract_examples,"max_tokens":8192,"timeout":40,
          "model":"solar-mini4","cases_sha256":hashlib.sha256(json.dumps(samples,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
          "prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    analyzer=SolarAnalyzer(load_api_key(),model="solar-mini4")
    rows=[]
    for sample in samples:
        row={"id":sample["id"],"matched":False};trace={};started=time.monotonic()
        try:
            reply,model,pt,ct=analyzer._request_review(sample["document"],sample["profile"],
                reasoning_effort=args.effort,timeout=40,_trace=trace,prompt=prompt)
            issues=validate_review(reply,sample["profile"],len(sample["document"].splitlines()))
            row.update(assess_review(issues,sample["expected"]))
            row.update(issues=issues,model=model,prompt_tokens=pt,completion_tokens=ct)
        except AnalysisError as error:row["error"]=error.code
        except ReviewValidationError:row["error"]="SEMANTIC_REVIEW_INVALID"
        trace.pop("raw",None)
        row["elapsed_ms"]=round((time.monotonic()-started)*1000)
        rows.append(row)
        (args.output/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        print(json.dumps(row),flush=True)
    return 0 if all(row["matched"] for row in rows) else 1

if __name__=="__main__":
    raise SystemExit(main())
