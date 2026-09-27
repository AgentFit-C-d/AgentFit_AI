import json,hashlib,argparse
from pathlib import Path
from .anchored_analysis import AnchoredAnalyzer,CANDIDATE_PROMPT,JUDGMENT_PROMPT
from .evaluate import load_api_key
from .solar import AnalysisError
from .profile import FIELDS
from .semantic_review import REVIEW_PROMPT, REVIEW_MAX_TOKENS

def safe_diagnostics(diagnostic):
 numeric=("call","elapsed_ms","provider_elapsed_ms","request_bytes","response_bytes","prompt_tokens","completion_tokens","max_tokens")
 allowed={
  "stage":{"candidate_generation","judgment","semantic_review","semantic_repair","semantic_recheck"},
  "outcome":{"started","response_received","validated","semantic_failed","validation_failed","failed"},
  "reasoning_effort":{"none","low","medium"},
 }
 calls=[]
 for call in diagnostic.get("calls",[]):
  item={k:call[k] for k in numeric if k in call and (call[k] is None or type(call[k]) is int and call[k]>=0)}
  item.update({k:call[k] for k,values in allowed.items() if call.get(k) in values})
  # Error codes are generated locally, never provider text.
  if "error" in call and type(call["error"]) is str and call["error"].isascii() and call["error"].replace("_","").isupper():
   item["error"]=call["error"]
  issues=[]
  for issue in call.get("semantic_issues",[]):
   if issue.get("field") in FIELDS and issue.get("kind") in ("unsupported","wrong_role","wrong_scope","uncertainty","missing","overbroad","duplicate"):
    issues.append({"field":issue["field"],"kind":issue["kind"]})
  if issues:item["semantic_issues"]=issues
  calls.append(item)
 result={"calls":calls}
 elapsed=diagnostic.get("elapsed_ms")
 if type(elapsed) is int and elapsed>=0:result["elapsed_ms"]=elapsed
 return result


def main():
 parser=argparse.ArgumentParser(description="Fixed tuning-only semantic pilot; not a service-readiness gate.")
 parser.add_argument("--live",action="store_true")
 parser.add_argument("--review-effort",choices=("medium","low"),default="medium")
 parser.add_argument("--output",type=Path,required=True)
 args=parser.parse_args()
 if not args.live:parser.error("--live required")
 cases=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/quote-extraction-cases.json').read_text(encoding='utf-8'))
 gold=[
  {"features":[["장소 확인"],["후보 선택"]]},
  {"features":[["회원 승인을 요청","회원 승인을 요청한다","사용자는 회원 승인을 요청한다","사용자는 회원 승인을 요청한다."],
               ["회원 승인을 처리","회원 승인을 처리한다","운영자는 회원 승인을 처리한다","운영자는 회원 승인을 처리한다."]]},
  {},
  {"external_integrations":[]},
  {},
  {"features":[["일정 추천"]]}
 ]
 root=args.output
 root.mkdir(parents=True,exist_ok=False)
 plan={"model":"solar-mini4","cases_sha256":hashlib.sha256((Path(__file__).resolve().parents[1]/'tests/fixtures/quote-extraction-cases.json').read_bytes()).hexdigest(),
  "gold":gold,"candidate_prompt_sha256":hashlib.sha256(CANDIDATE_PROMPT.encode()).hexdigest(),
  "judgment_prompt_sha256":hashlib.sha256(JUDGMENT_PROMPT.encode()).hexdigest(),
  "review_effort":args.review_effort,"review_max_tokens":REVIEW_MAX_TOKENS,
  "review_prompt_sha256":hashlib.sha256(REVIEW_PROMPT.encode()).hexdigest(),
  "semantic_scoring_revision":1,"planned":6,"rule":"all six semantic profiles match, no provider or validation error; only then repeat twice"}
 (root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
 a=AnchoredAnalyzer(load_api_key(),model='solar-mini4',review_effort=args.review_effort)
 rows=[]
 for case,expected in zip(cases,gold):
  row={"id":case["id"],"passed":False}
  try:
   result=a.analyze(case["document"],case["id"])
   data=result.profile["data"];mismatches=[]
   for field,value in data.items():
    if field not in expected:
     if value is not None:mismatches.append(field)
    elif expected[field]==[]:
     if value!=[] or result.profile["sources"][field]!="DOCUMENT":mismatches.append(field)
    else:
     aliases=expected[field]
     if type(value) is not list or len(value)!=len(aliases) or not all(sum(v in group for v in value)==1 for group in aliases):
      mismatches.append(field)
   row.update(passed=not mismatches,mismatch_fields=mismatches,provider_calls=result.provider_calls,
              elapsed_ms=result.elapsed_ms,model=result.model,first_pass=result.first_pass_validated)
   row.update(safe_diagnostics(result.diagnostics))
  except AnalysisError as error:
   row["error"]=error.code
   diag=getattr(error,"diagnostics",{})
   row.update(safe_diagnostics(diag))
  rows.append(row)
  (root/'attempts.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
  print(json.dumps(row),flush=True)
 (root/'results.json').write_text(json.dumps({"planned":6,"passed":sum(r["passed"] for r in rows),"rows":rows},indent=2),encoding='utf-8')

 return 0 if len(rows)==6 and all(r["passed"] for r in rows) else 1

if __name__=="__main__":
 raise SystemExit(main())
