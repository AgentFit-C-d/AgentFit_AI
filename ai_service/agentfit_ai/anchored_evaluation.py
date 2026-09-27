import json,hashlib,argparse
from pathlib import Path
from .anchored_analysis import AnchoredAnalyzer,CANDIDATE_PROMPT,JUDGMENT_PROMPT
from .evaluate import load_api_key
from .solar import AnalysisError

def main():
 parser=argparse.ArgumentParser(description="Fixed tuning-only semantic pilot; not a service-readiness gate.")
 parser.add_argument("--live",action="store_true")
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
  "semantic_scoring_revision":1,"planned":6,"rule":"all six semantic profiles match, no provider or validation error; only then repeat twice"}
 (root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
 a=AnchoredAnalyzer(load_api_key(),model='solar-mini4')
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
  except AnalysisError as error:
   row["error"]=error.code
   diag=getattr(error,"diagnostics",{})
   row["calls"]=[{k:c[k] for k in ("stage","outcome","error") if k in c} for c in diag.get("calls",[])]
  rows.append(row)
  (root/'attempts.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
  print(json.dumps(row),flush=True)
 (root/'results.json').write_text(json.dumps({"planned":6,"passed":sum(r["passed"] for r in rows),"rows":rows},indent=2),encoding='utf-8')

 return 0 if len(rows)==6 and all(r["passed"] for r in rows) else 1

if __name__=="__main__":
 raise SystemExit(main())
