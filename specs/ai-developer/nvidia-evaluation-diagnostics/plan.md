# NVIDIA Evaluation Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. User approved direct autonomous execution; no repeated approval.

**Goal:** 선택형 평가에서 실제 호출의 실패 모델·단계를 원문 없이 보존한다.
**Architecture:** 엄격한 메타데이터 계약을 분석 자식 envelope에 연결하고 부모가 검증한다. 별도 freeze/진단 결과 행을 NVIDIA evaluator에 연결한다. 기본 공개 응답은 유지한다.
**Tech Stack:** Python unittest/asyncio/FastAPI/LangExtract, 기존 NVIDIA streaming transport.
**Spec:** specs/ai-developer/nvidia-evaluation-diagnostics/spec.md

## Global Constraints

- 외부 호출0/유료0/재시도0/배포0, 이전 실제 결과 재시작 금지.
- 모델/공개Profile/기본분석기/64호출/1800초/무료확인 정책 유지.
- 합성30초·timeout10초/대상120초/suite180초/CI관찰10분, 구현60분마다 상태 점검.
- 진단은 최대64개 허용 메타데이터만. unavailable은 실제0호출을 뜻하지 않는다.

## Review Focus

1. 알 수 없는 필드/모델/코드/키·원문을 통한 누출: Task1 엄격한 계약 거절 시험.
2. 성공/실패 응답이 조작된 진단을 동반: Task1 부모의 envelope/result/diagnostics 검증 및 기본 경로 거절 시험.
3. 진단이 추출·호출 수·점수를 바꿈: Task2 실제 SDK on/off 동등성 시험.
4. timeout/cancel 후 호출 수를0으로 기록하거나 자식을 남김: Task2 실제 provider 진입 뒤 종료 시험.
5. 진단 결과 손상/없는 진단/구형 폴더 섞임/실패 후 재시작: Task2 checkpoint와 무료 예산 회귀 시험.

### Task 1: 호출 메타데이터 내부 계약과 프로세스 연결

**Files:**
- Create: ai_service/agentfit_ai/analysis_call_metadata.py
- Modify: ai_service/agentfit_ai/{candidate_service_worker,analysis_worker,analysis_process}.py
- Create: ai_service/tests/test_analysis_call_metadata.py

**Interfaces:**
- Produces: `METADATA_VERSION`, `validate_metadata(value) -> dict`, `unavailable_metadata(reason) -> dict`, `build_metadata(calls, failure_stage=None) -> dict`.
- Produces: `run_analysis_process(..., call_diagnostics: dict | None = None)` empties-only sink; only nvidia_only=True. Normal result unchanged. Worker `diagnostics=METADATA_VERSION` tag opts in.
- Consumes: existing call_trace rows, PIPELINE_FAILURE_CODES, SAFE_CODES, allowed NVIDIA two models.

- [ ] Step 1: RED contract tests for64 limit/strict types/contiguous call indices/attempt1/no retry/known stage+model+code/unknown keys, unavailable explicit null reason semantics.
- [ ] Step 2: Implement strict pure builders/validator. Expected targeted unit tests GREEN.
- [ ] Step 3: RED worker/parent tests for optional envelope, stage/model trace on failure, invalid sink/trace/result/default envelope rejection; timeout unavailable and no accepted partial diagnostics.
- [ ] Step 4: Wire optional trace in candidate_service_worker, analysis_worker envelope and bounded parent parsing. Default pipeline arguments/output unchanged when disabled.
- [ ] Step 5: Commit and task-done targeted module: `python -m unittest tests.test_analysis_call_metadata -v`. Expected all pass.

### Task 2: 평가 기록·CLI·실제 자식 통합 검증

**Files:**
- Modify: ai_service/agentfit_ai/{nvidia_evaluation_inputs,nvidia_evaluation_runner,independent_evaluation_runner}.py
- Create: ai_service/tests/test_nvidia_evaluation_diagnostics.py
- Create: ai_service/runtime_tests/test_nvidia_diagnostics_runtime.py
- Create: specs/ai-developer/nvidia-evaluation-diagnostics/{freeze,validation,review}.json/md as applicable

**Interfaces:**
- Consumes: Task1 run_analysis_process call_diagnostics sink and strict metadata helpers.
- Produces: build_freeze/prepare_evaluation `call_diagnostics=False` option, distinct variant/settings/manifest; CLI --call-diagnostics; rows diagnostics required only for new variant.
- Shared checkpoint reader gains optional `row_validator=None`, default uses existing validation. NVIDIA wrapper validates diagnostics then existing base row, preserving original immutable files.

- [ ] Step 1: RED opt-in preflight/CLI/checkpoint tests, malformed diagnostics and previous failure resume rejection. Add run_scored_process optional diagnostics sink preserving score-only return.
- [ ] Step 2: Minimal opt-in registration, row validation, persistence and CLI implementation. Explicit unknown diagnostics on child failure; no automatic additional model calls.
- [ ] Step 3: Real child/SDK loopback normal on/off score and call equality, review-stage503/requested GLM, initial429/requested DeepSeek, malformed candidate semantic error, timeout/cancel process/socket cleanup. Expected runtime GREEN.
- [ ] Step 4: Offline fresh freeze for existing10docs/207provisionalgold; verify previous gold/results unchanged, no .env/model calls. Document current result and bounds; commit.
- [ ] Step 5: task-done runs unit/runtime/contract/core suites once, each180sec. Expected exit0 with platform skips reported. Single final independent review; important fixes RED→GREEN, no re-review; feature push + exact codeSHA CI.
