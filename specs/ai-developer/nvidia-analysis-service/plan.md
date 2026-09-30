# NVIDIA 단독 서비스 연결 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. 직접 순차 구현. 목표 내 설계·계획 자율 승인 적용, 최종 독립 리뷰1회.

**Goal:** NVIDIA 단독 분석을 실제 HTTP/요청 자식/기한/사용자 확인 mock 흐름에 연결한다.
**Architecture:** 선택형 integrated-nvidia → nvidia_only process flag/엄격 stdin → execute_nvidia_analysis → 기존 NVIDIA-only engine → 기존 v2 검증/MockStore.
**Tech Stack:** 기존 Python3.13/unittest/FastAPI/LangExtract1.7.0/httpx/uvicorn/jsonschema, 새 의존성 없음.
**Spec:** specs/ai-developer/nvidia-analysis-service/spec.md

## Global Constraints

- feature/nvidia-analysis-service, base95aff7678b11c9e6d5612f4bc55803f1f81c6a90, 기존 독립 worktree 재사용. 원래 analysis-runtime 기준선 보존.
- 기본 모드/공개 Profile/v2/평가 runner 불변. 외부 모델0·유료0·배포0·자동재시도0. 계정 무료 한도/실모델 품질/실제 Spring 미검증.
- 요청 기본1800초·최대3600초·모델64회. 작업45분 점검, suite180초, 합성 요청30초/기한테스트10초/mock45초, 종료3~5초.

## Review Focus

1. NVIDIA 모드가 Solar 키를 요구·전달하거나 유료 fallback을 하는가 — Solar 키 없는 환경, 금지 Solar shim, 모든 통신 nvidia assert.
2. flag 충돌/키 혼합으로 다른 분석기가 실행되는가 — 프로세스 생성 전 거부, 정확한 네 필드 stdin·v2 검증.
3. 전체 기한/취소가 자식과 통신에 적용되지 않는가 — 실제 통신 진입 확인 후 timeout/TCP 종료/ASGI 취소, 소켓/프로세스 종료·다음 요청 성공.
4. 429/503/구조 오류가 재시도나 부분 성공을 만드는가 — 실패1호출/안전 코드, 명시적 재요청만 복구.
5. 성공을 확인 저장 완료로 오인하는가 — mock DRAFT→명시적 수정/CONFIRMED→409/삭제, Spring 실제 연동 미검증 기록.

### Task 1: API부터 단독 자식 분석과 mock 확인까지 연결

**Files:** Modify ai_service/agentfit_ai/{analysis_process,analysis_worker,candidate_service_worker,http_service}.py; Create tests/test_nvidia_service.py; Modify runtime_tests/test_integrated_service.py, runtime_tests/integrated_service_fixture.py; Create runtime_tests/test_nvidia_service_runtime.py; Modify core_flow_tests/test_core_flow_runtime.py; Create core_flow_tests/test_nvidia_core_flow.py; Modify README.md, Docs/api/analysis-confirmation-v2.draft.md, Docs/api/core-analysis-mock-handoff.md; Create validation.md와 work/harness/nvidia-analysis-service/STATE.md.
**Interfaces:** 명세의 execute_nvidia_analysis와 nvidia_only bool, mode integrated-nvidia. fixture service(...,analysis_mode='integrated-candidates')와 core_flow(...,analysis_mode='integrated-candidates')는 기존 기본을 보존한다. Provider는 요청 kind를 기록하고 선택적인 failure_status를 합성 HTTP 응답으로 반환한다. NVIDIA shim은 Solar transport를 금지하고 기존 loopback/자식 생성 금지를 유지한다.

- [x] Step1: test_nvidia_service.py에 worker/실제 프로세스 stdin/v2/HTTP 모드·키·기한·실패 검증을 작성한다. Run `python -m unittest discover -s tests -p test_nvidia_service.py`. Expected: 지원되지 않는 모드/옵션으로 실패, 외부0.
- [x] Step2: 네 제품 파일에 명세의 모드·키·기한·안전 오류 계약을 연결한다. 기존 중복 error/projection만 최소 공통 함수로 옮길 수 있다. 위 명령 GREEN과 기존 통합 worker/process/HTTP 회귀. Expected: Solar 키 없이 단독 v2, 기존 혼합 호출은 같은 함수·인자를 유지.
- [x] Step3: 실제 단독 SDK/자식/HTTP/SSE runtime5개 경계와 공개 mock 연결을 작성해 실행한다. fixture의 새 인자 부재 RED를 확인하고, 기본값을 유지하는 옵션만 추가한다. Run 신규 runtime/core 파일. Expected: 성공/429/503/timeout/TCP취소/ASGI취소/명시적 재요청/확인 저장·409·삭제 증거.
- [x] Step4: README와 인계 문서에 새 모드/키/기한/로컬 검증과 실환경 미검증을 기록한다. 전체 네 suite 각180초 gate, commit/task-done. Expected: 기존+신규 통과, 품질평가 파일과 기존 baseline 변경 없음.
- Step5 (리뷰 완료; push 이후 게이트 결과는 ledger에 기록): 독립 최종 리뷰1회→중요 결함은 RED/GREEN1수정pass→feature push→정확한 SHA의 CI. SDD/작업 폴더 보존. Expected: 핵심 흐름 연결 범위와 미검증 항목을 구분해 보고.

## 자기 검토

한 작업에서 직렬 계약을 끝까지 연결한다. 새 모드가 baseline 의미를 바꾸지 않고 전체 기한을 공유하도록 명시했다. 외부 모델이나 실제 Spring 없이 가능한 검증 범위를 넘어 성공을 주장하지 않는다.
