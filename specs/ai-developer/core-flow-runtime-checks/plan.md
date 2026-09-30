# 핵심 흐름 연결 검증 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. 사용자가 선택한 직접 구현을 유지하며, 목표의 자율 진행 승인에 따라 설계·계획 재승인을 묻지 않는다.

**Goal:** 실제 SDK·작업자의 v2 결과를 공개 mock 초안·확인 저장과 연결해 검증한다.
**Architecture:** 기존 runtime service fixture→기존 mock TCP fixture→전용 core_flow_tests. 제품 코드는 변경하지 않으며 관측된 결함이 있을 때만 최소 수정한다.
**Tech Stack:** Python3.13, unittest, 기존 FastAPI/httpx/uvicorn/LangExtract/jsonschema.
**Spec:** specs/ai-developer/core-flow-runtime-checks/spec.md

## Global Constraints

- feature/core-flow-runtime-checks, base a5657b4bb07598dbf681d777e28c71aac9f23ffb. 완료된 기존 독립 worktree를 재사용하며 원래 analysis-runtime 기준선은 보존한다.
- 현재 API 계약·제품 코드·모델·프롬프트·기본 timeout 불변. 실제 Spring·모델 의미 품질·운영 개인정보 처리는 미검증 유지.
- 작업45분 점검, suite180초, child30초/mock45초/진입12초/정리3~5초, 테스트 복구 요청1회/실패 자동재시도0/외부 모델0회/유료0원.

## Review Focus

1. 실제 SDK/작업자를 거치지 않고 고정 callback을 통과시켜 연결 성공으로 오인하는가 — 실제 단계별 Provider schema·작업자 수/종료·10필드 확인.
2. 공개 취소·mock timeout이 자식과 Provider까지 전파되지 않는가 — 살아 있는 통신을 확인한 뒤 취소/실제 timeout 만료와 종료 검증.
3. 실패/응답 재전송이 이전 확인값을 덮거나 중복 저장하는가 — 성공 이후 실패·재시도·동일 버전409 및 재조회.
4. 합성 Provider로 조용히 외부에 연결하거나 비밀을 출력하는가 — 부모/자식 loopback 제한, 고정 합성 키, 오류 표식 검사.
5. CI가 새 필수 suite를 건너뛰거나 의존성을 기본 환경에 섞는가 — 전용 CI job, optional 통합+mock 의존성, pip check, 정확한 HEAD 확인.

### Task 1: 실제 분석부터 확인 저장까지 연결

**Files:** Modify ai_service/runtime_tests/test_integrated_service.py(service fixture 내부 토큰 옵션); Create ai_service/core_flow_tests/test_core_flow_runtime.py; Modify .github/workflows/ai-linux.yml, Docs/api/core-analysis-mock-handoff.md; Create 이 명세 폴더 validation.md와 work/harness/core-flow-runtime-checks/STATE.md.
**Interfaces:** 기존 service(provider,timeout=30)에 internal_token='synthetic-internal' 추가. 새 suite는 service(...,internal_token='mock-internal')의 ai_app을 running_server(ai_app=...,store=...,analysis_timeout_seconds=45)에 주입한다. 기존 Provider.reply/SHIM/실제 run_analysis_process는 재사용한다. 제품 공개 서명은 바꾸지 않는다.

- [ ] Step1: 전용 suite에 명세5개 경계 사례 작성. 기존 fixture에 없는 internal_token 인자를 호출하는 연결 준비 테스트로 누락을 확인한 뒤 기본값 보존 옵션만 추가한다. Expected: 최초 fixture 연결 실패→통합 성공 또는 구체적 제품 결함 재현. 기존 기능 검증 추가의 특성상 성공을 위해 제품을 임의로 고장내지 않는다.
- [ ] Step2: 실제 SDK 10필드→DRAFT→수정/확인→재접속→409→삭제, malformed Provider→502/보존/명시적 재시도, 두 Provider별 공개 disconnect, 결정적으로 만료한 mock timeout을 실행한다. Expected: 명세 상태·버전·작업자/소켓 종료·합성 키 미출력. 실패 시 systematic-debugging 후 최소 RED/GREEN 수정.
- [ ] Step3: 전용 CI job에 통합+mock 고정 의존성과 pip check/전용 suite를 추가한다. 문서에 실제 통과 범위와 ASGI/메모리/합성 한계를 적는다. Expected: CI 구조가 suite를 생략하지 않음, 계약/제품 의존성 불변.
- [ ] Step4: 기존 unit/runtime/contract와 새 core_flow_tests를 각180초 상한으로 실행하고 결과 기록·commit/task-done. Expected: 기존 동작·모든 필수 연결 사례 통과.
- [ ] Step5: 전체 독립 리뷰1회→Critical/Important만1수정pass+회귀→feature push→정확한 CI. 사용자 지침에 따라 SDD/작업 폴더 보존. Expected: 검증 증거와 미검증 항목을 분리해 보고.

## 자기 검토

명세1~5를 한 전용 suite로 연결하며 제품과 실제 환경 범위를 구분했다. 기존 fixture 재사용 외에 새 연결 구현은 없다. 테스트 자체 추가가 목적이므로 baseline 성공은 허용하고 결함 발견 시에만 제품 회귀를 수정한다.
