# 안전한 분석 실패 단계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. 기존선택인직접순차구현을유지한다. 자율진행승인을적용해설계/계획재승인을묻지않는다.

**Goal:** 일반ANALYSIS_FAILURE에가려진신뢰된실패단계를기존error문자열로보존한다.
**Architecture:** diagnostics 고정allowlist→candidate worker 우선순위→기존process/FastAPI/evaluation validator 그대로 재사용.
**Tech Stack:** 기존Python3.13/unittest/표준라이브러리. 새의존성없음.
**Spec:** specs/ai-developer/analysis-failure-stages/spec.md

## Global Constraints

- 새feature/analysis-failure-stages,baseef6fad5; 기존analysis-runtime와평가자료/결과를수정하지않는다.
- 외부모델0회/유료0원,원문·키·예외로그0,공개Profile/추가DTO/모델·프롬프트·호출기한변경0.
- 작업45분점검/명령180초/합성process10초/자동재시도0. 실제Spring·모델품질은미검증유지.

## Review Focus

1. 알려진Provider오류/호출한도를stage로덮어쓰지않는가(우선순위표테스트).
2. 비문자열·임의stage/detail/key가예외나진단에노출되지않는가(민감sentinel·비문자열회귀).
3. worker에서만통과하고부모프로세스/FastAPI가새코드를거절하지않는가(실제child경계와HTTP검증).
4. 새코드가실패를invalid/success로오채점하거나분모를줄이지않는가(실제평가worker+protocol).
5. 고정baseline자료나oldrun에변경을혼합하지않는가(기존checkout해시·신규branch명시).

### Task 1: 단계 오류 코드 보존과 경계 검증

**Files:** Modify ai_service/agentfit_ai/diagnostics.py,candidate_service_worker.py; Create ai_service/tests/test_pipeline_failure_stages.py 및 tests/fixtures/failing_candidate_worker.py; Doc ai_service/README.md 및 이명세폴더validation.md/work/harness/analysis-failure-stages/STATE.md.
**Interfaces:** `PIPELINE_FAILURE_CODES: frozenset[str]`(명세9개); execute_integrated_analysis 서명·실패DTO불변. `_provider_worker_environment`와기존run_analysis_process(command=...)테스트주입사용. fixture는합성pipeline예외만발생시키며네트워크없음.

- [ ] Step1: test_pipeline_failure_stages.py에9개단계,known provider/limit우선,unknown/list/dict단계fallback,평가실패분모보존의실패테스트작성/실행. Expected:knownstage가현재ANALYSIS_FAILURE이므로RED. 성공회귀는기존worker테스트를함께실행한다.
- [ ] Step2: diagnostics고정집합과worker조건분기만추가. Expected: 새테스트GREEN,원문/키/sentinel부재,새예외문자열출력없음.
- [ ] Step3: 실제child fixture→run_analysis_process→FastAPI create_app(analyze=합성callback) 및evaluation worker/validate_score의경계검증. 모델/API키없는합성입력,deadline10초,반환error일치·실패분모/releasefalse검사.
- [ ] Step4: 새branch cwdai_service에서 기존전용환경 E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe로unit/runtime/contract전체gate(각180초). 원래worktree의기준선preflight불변재확인. 문서와결과기록,commit/task-done.
- [ ] Step5: 기능전체독립review1회→Important/Critical만RED/GREEN1수정pass→featurepush/정확한CI. 기존checkout와SDD자료보존,merge/배포하지않는다.

## 검토

명세의오류우선순위/원문미출력/분모불변/기준선보존이각테스트에연결된다. 큰계약/모델변경없이관측정보손실만해결한다. 이미승인된직접구현으로진행한다.
