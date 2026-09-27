"""Single-process evaluation instrumentation. Never imported by the service path."""
from unittest.mock import patch
from .profile import FIELDS
from .solar import AnalysisError
from .source_repair import apply_repairs
from .anchored_evaluation import safe_diagnostics

def score_profile(profile, gold):
    fields={};bad=[]
    for field in FIELDS:
        actual=profile["data"][field]
        expected=gold.get(field)
        if expected is None:
            matched=actual is None
            detail={"expected_state":"unknown","matched":matched}
        elif expected==[]:
            matched=actual==[] and profile["sources"][field]=="DOCUMENT"
            detail={"expected_state":"absent","matched":matched}
        elif type(expected) is str:
            matched=actual==expected
            detail={"expected_state":"scalar","matched":matched}
        else:
            values=actual if type(actual) is list else []
            # Maximum one-to-one assignment prevents overlapping aliases from double counting.
            owner={}
            def assign(group, seen):
                for i,value in enumerate(values):
                    if i not in seen and value in expected[group]:
                        seen.add(i)
                        if i not in owner or assign(owner[i],seen):
                            owner[i]=group
                            return True
                return False
            exact=sum(assign(group,set()) for group in range(len(expected)))
            covered=sum(any(alias in value for alias in group for value in values) for group in expected)
            matched=type(actual) is list and len(values)==len(expected) and exact==len(expected)
            detail={"expected_state":"array","matched":matched,"actual_items":len(values),
                    "expected_groups":len(expected),"exact_groups":exact,"covered_groups":covered}
        fields[field]=detail
        if not matched:bad.append(field)
    return {"passed":not bad,"mismatch_fields":bad,"fields":fields}

def observe_run(analyzer, document, document_id, gold):
    """Observe pure repair output and review input without sending gold to the provider.
    Patches are scoped and restored even on errors. This tool is for sequential CLI use only.
    Observation work counts against the existing wall-clock budget.
    """
    snapshots=[];repairs=[]
    original_review=analyzer._request_review
    def review(source,profile,**kwargs):
        snapshots.append(score_profile(profile,gold))
        return original_review(source,profile,**kwargs)
    def repair(*args,**kwargs):
        result=apply_repairs(*args,**kwargs)
        repairs.append(score_profile(result,gold))
        return result
    row={"passed":False}
    with patch.object(analyzer,"_request_review",side_effect=review), patch(
            "agentfit_ai.anchored_analysis.apply_repairs",side_effect=repair):
        try:
            result=analyzer.analyze(document,document_id)
            final=score_profile(result.profile,gold)
            row.update(passed=final["passed"],final=final,first_pass=result.first_pass_validated)
            diagnostic=result.diagnostics
        except AnalysisError as error:
            row["error"]=error.code
            diagnostic=error.diagnostics or {}
    row.update(review_inputs=snapshots,repairs=repairs)
    row.update(safe_diagnostics(diagnostic))
    return row

def main():
    import argparse,hashlib,json
    from pathlib import Path
    from .anchored_analysis import AnchoredAnalyzer
    from .anchored_prompts import CANDIDATE_PROMPT_V2,JUDGMENT_PROMPT_V2
    from .source_repair import SOURCE_REPAIR_PROMPT
    from .repair_examples import REPAIR_EXAMPLES
    from .review_examples import REVIEW_EXAMPLES
    from .semantic_review import REVIEW_PROMPT
    from .evaluate import load_api_key
    parser=argparse.ArgumentParser(description="Fixed four-case repair/review observation; not a readiness gate.")
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--repair-examples",action="store_true")
    parser.add_argument("--review-examples",action="store_true")
    parser.add_argument("--review-expression",action="store_true")
    parser.add_argument("--all-pilot-cases",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error("--live required")
    repo=Path(__file__).resolve().parents[2]
    base=json.loads((repo/"ai_service/tests/fixtures/quote-extraction-cases.json").read_text(encoding="utf-8"))
    gold=json.loads((repo/"specs/ai-developer/04-analysis-provider/anchored-candidates/pilot-plan.json").read_text(encoding="utf-8"))["gold"]
    cases=[dict(c,gold=g) for c,g in zip(base,gold)]
    cases+=json.loads((repo/"specs/ai-developer/04-analysis-provider/anchored-prompt-contract/new-cases.json").read_text(encoding="utf-8"))
    if not args.all_pilot_cases:
        cases=[c for c in cases if c["id"] in ("Q-001","Q-002","Q-004","N-004")]
    from .expression_review import expression_prompt
    review_prompt=expression_prompt() if args.review_expression else REVIEW_PROMPT
    args.output.mkdir(parents=True,exist_ok=False)
    plan={"scope":"pilot_twelve_cases" if args.all_pilot_cases else "diagnostic_four_cases","model":"solar-mini4","prompt_revision":"v2","source_repair":True,
          "review_effort":"low","repair_examples":args.repair_examples,"review_examples":args.review_examples,"review_expression":args.review_expression,"planned":len(cases),
          "cases_sha256":hashlib.sha256(json.dumps(cases,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
          "prompt_sha256":[hashlib.sha256(p.encode()).hexdigest() for p in
                          (CANDIDATE_PROMPT_V2,JUDGMENT_PROMPT_V2,SOURCE_REPAIR_PROMPT+(REPAIR_EXAMPLES if args.repair_examples else ""),review_prompt+(REVIEW_EXAMPLES if args.review_examples else ""))],
          "observer_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
    analyzer=AnchoredAnalyzer(load_api_key(),model="solar-mini4",prompt_revision="v2",source_repair=True,review_effort="low",repair_examples=args.repair_examples,review_examples=args.review_examples,review_expression=args.review_expression)
    rows=[]
    for case in cases:
        row={"id":case["id"],**observe_run(analyzer,case["document"],case["id"],case["gold"])}
        rows.append(row)
        (args.output/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        print(json.dumps({"id":row["id"],"passed":row["passed"],"error":row.get("error"),
                          "review_inputs":[x["passed"] for x in row["review_inputs"]],
                          "repairs":[x["passed"] for x in row["repairs"]],"elapsed_ms":row.get("elapsed_ms")}),flush=True)
    return 0 if all(r["passed"] for r in rows) else 1

if __name__=="__main__":
    raise SystemExit(main())
