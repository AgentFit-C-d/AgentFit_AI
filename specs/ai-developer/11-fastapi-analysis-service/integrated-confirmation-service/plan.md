# 통합 확인형 서비스 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 지정 직접 순차 구현과 목표 내 자율 권한을 유지한다.

**Goal:** 기존 통합 후보 분석을 버전이 명확한 확인 응답과 요청별 취소 가능한 실제 HTTP 경로로 연결한다.
**Architecture:** 후보 결과→confirmation-v2 어댑터→analysis_worker/process→FastAPI. 모델 통신은 요청 worker 안에서 직접 실행하고 부모가 전체 기한과 연결 종료를 관리한다.
**Tech Stack:** Python3.13, FastAPI/uvicorn, unittest/httpx, LangExtract1.7.0, 기존 urllib/SSE.
**Spec:** specs/ai-developer/11-fastapi-analysis-service/integrated-confirmation-service/spec.md

## Global Constraints

- feature/integrated-confirmation-service; base24351e0d84ee0ccd015ea1dfc50692412b8aaa9c, 기존 isolated analysis-runtime checkout 재사용.
- 기본서비스·v1·공개Profile·분석의모델/의미/기본20설정 유지. v2만 unresolved에검증된non-null제안허용,항상확인필요.
- 통합모드전체기한1800/최대3600초,기존모드60/최대120초. slot/upload 기존값 유지.
- 외부API/비공개문서/실제키사용0. 실제SDK와로컬합성Provider로검증. 공용환경수정없음.
- 기준전체1045개1040pass/5skip·SDK4/4,직전exactCI36705765562두job성공. 새task완료gate는전체tests/runtime_tests.

## Review Focus

1. 비null unresolved·빈배열·전역누락·후보0에서 제안 손실이나 확인 질문 누락이 없는가.
2. v1/v2·mode·키·환경기한이 혼용돼 잘못된 경로나 자동완료가 허용되지 않는가.
3. 긴헤더/heartbeat·SDK thread·동시요청에서 실제 통신중 취소가 worker와연결을 정리하고 슬롯을 반환하는가.
4. 손상된 Profile/metadata/모델응답이나 실패예외가 경계를 지나 원문·키·임의질문을 노출하지 않는가.
5. 로컬 전체경로 검증과 모델 의미정확도·Spring저장·배포완료를 구분하는가.

### Task 1: 후보 확인 응답 계약

**Files:** Create ai_service/agentfit_ai/candidate_confirmation.py, ai_service/tests/test_candidate_confirmation.py. Modify ai_service/agentfit_ai/profile.py, http_service.py(공통Profile 재검증만).
**Interfaces:**
- Produces `check_profile_snapshot(document: str, document_id: str, profile: dict) -> dict` in profile.py: 기존 http_service._checked_profile 검증을 공유하며 exact snapshot 일치가 필요하다.
- Produces `project_candidate_confirmation(document, document_id, result) -> dict`, `validate_candidate_confirmation(document, document_id, outcome) -> dict` in candidate_confirmation.py. spec의 exact v2 키/상태/질문/사유를 사용한다. 실패 outcome은 Task2/3 경계에서 별도로 검증한다.
- Consumes finalize_candidate_analysis 결과: outcome,profile,unresolvedFields,rejectedCandidateCount,candidateCount,rejectedReasons,reviewIssueCount; featureCuration은 선택.

- [ ] Step 1: groundednon-nullunresolved보존,확정후보suggested질문,unknown/[],전역불확실·후보0,입력불변,잘못된doc/span/sources/unknownFields,모순된candidate_profile,metadata오류,질문중복/누락/사유/상태/v1/complete 거부테스트를작성한다.
- [ ] Step 2: `python -m unittest discover -s tests -p test_candidate_confirmation.py -v`. Expected:새함수/모듈부재RED.
- [ ] Step 3: 공통Profile재검증을이동하고순수v2어댑터/검증기를구현한다. 출력은허용키와코드만새로생성한다.
- [ ] Step 4: 새테스트와test_profile/test_http_service를실행한뒤전체tests/runtime_tests. Expected:기존5skip외통과/기본응답호환.
- [ ] Step 5: 구현·테스트commit, task-done전체gate. Expected:검증증거와완료ledger.

### Task 2: 단일 분석 프로세스에 통합 파이프라인 연결

**Files:** Modify nvidia_streaming.py, analysis_worker.py, analysis_process.py, diagnostics.py. Create candidate_service_worker.py, tests/test_candidate_service_worker.py; extend tests/test_nvidia_streaming.py, tests/test_analysis_process.py.
**Interfaces:**
- Produces `post_nvidia_streaming_inline(payload, api_key, timeout) -> bytes`; 기존streaming의입력/출력검증을공유하고 직접nvidia_stream_worker._fetch를호출한다. 별도프로세스없음.
- Produces `execute_integrated_analysis(document, document_id, solar_key, nvidia_key) -> dict` in candidate_service_worker.py. 실제analyze_integrated_candidates+Task1어댑터, Solar/NVIDIA inline transports. SDK없으면 INTEGRATED_RUNTIME_UNAVAILABLE 안전오류.
- Extends `run_analysis_process(..., recoverable_solar=False, integrated_candidates=False, nvidia_key=None, command=None)`. 모드는상호배타적이며새키는integrated일때만허용한다. worker stdin키집합은document/documentId/key/nvidiaKey/mode=integrated-candidates. 기존입력그대로유지.
- Produces v2확인응답 또는 exact `{contract,outcome:'failed',error}`. CandidatePipelineError의provider_code를safe_code로통과,예산오류CALL_LIMIT,나머지ANALYSIS_FAILURE. 원본예외미출력.

- [ ] Step 1: inline무자식/유효SSE·형식/크기/오류·입력불변,worker파이프라인/모드·키누출·실패/미설치·oversized,processv2프레이밍/키stdin/환경제거·mode혼용테스트작성.
- [ ] Step 2: 대상새테스트RED실행. Expected:새함수/옵션부재실패.
- [ ] Step 3: inline·worker·process를연결하고safe코드1개추가. 기존독립post_nvidia_streaming의자식deadline유지.
- [ ] Step 4: 대상전송/worker/process/Task1과전체tests/runtime_tests검증. Expected:기존대응회귀/모드정합성통과.
- [ ] Step 5: commit,task-done전체gate. Expected:두키가argv/env/error에없고v2만허용.

### Task 3: HTTP 모드·실 SDK/TCP 수명주기·인계

**Files:** Modify http_service.py, tests/test_http_service.py, README.md. Create tests/test_integrated_confirmation_http.py, runtime_tests/test_integrated_service.py, runtime_tests/integrated_service_fixture.py, specs/ai-developer/11-fastapi-analysis-service/integrated-confirmation-service/validation.md, work/harness/integrated-confirmation-service/{STATE.md,review.md,REMOTE.md}.
**Interfaces:** Consumes Tasks1/2. create_app의기존analysis_mode에integrated-candidates추가. `_run_default_analysis(..., integrated_candidates=False)`에서두키와모드를process로전달한다. v2검증은profile에유효한제안/질문을그대로전달한다.

- [ ] Step 1: exactv2header없음/중복/v1은body/slot/분석전428,기존v1/default회귀,완료/잘못된v2/질문오류502,두키누락503,긴환경기한/함수인자일치(120/1800/3600/3601/비숫자/bool)RED테스트작성·실행. Expected:새모드미지원실패.
- [ ] Step 2: HTTP모드·인증후계약확인·기한범위·새안전코드503·v2결과재검증연결. `_bounded_setting`문자길이는해당maximum자릿수로제한한다.
- [ ] Step 3: 실제SDK+로컬Provider용test-onlyworker shim 작성. LangExtract parser/추출/분류/검토/대표정리/어댑터는실제코드, endpoint만loopback고정. runtime_tests/test_integrated_service.py에서실제uvicornTCP정상요청을검증한다. Expected:합성문서10필드+근거+질문,외부통신0.
- [ ] Step 4: 로컬Solar와NVIDIA서버가응답시작Event를보낸뒤기한·취소·실TCPdisconnect를유발하는테스트작성·실행. 요청별worker PID/종료와ProviderEOF/연결종료,다음요청slot재사용을assert. Expected:가짜결과가아닌통신중중단을확인,자식Provider프로세스0.
- [ ] Step 5: 전체tests/runtime_tests,설정/실행/오류/v2예시·Spring미완료/품질한계README및validation기록,commit/task-done. Expected:회귀통과·실측과미검증구분.
- [ ] Step 6: fresh전체리뷰1회,필요시Critical/Important단일RED→GREEN수정,featurepush/정확한CI. Expected:기능연결완료와전체실사용미완료를구분한다.
