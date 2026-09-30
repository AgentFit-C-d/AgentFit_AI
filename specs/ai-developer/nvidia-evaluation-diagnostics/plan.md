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

### Task 3: 무료 범위의 실제 진단 평가

**목적:** 이전 PUBLIC-01 제공자 오류의 실패 모델·단계를 새 진단 기록으로 구분하고, 완료한 요청의 임시 정답 대비 품질을 측정한다. 이전 실패의 원인을 소급 확정하지 않는다.

**근거:** 사용자는 현재 NVIDIA 계정에서 DeepSeek4.1Flash·GLM5.3 무료 API 및 한도 초과 시 자동 결제 없는 거절을 명시 확인했다. 목표 내 자율 실행 승인을 적용한다. Task1~2의 외부0은 구현·로컬 검증 예산이며 이번 후속 측정은 아래 별도 상한을 적용한다.

**고정 입력:** 코드 `5d75535fdb2d6663db7ec40b7fab42b7339a5413`와 동일한 현재 코드, `nvidia-call-diagnostics-v1`, freeze `5d54bef56f15e2bb08c9e4da2b953d2b3275df8d7d467c97ce0157955f50e948`, 공개10문서·임시gold207개·문서당3회. 모델·scorer·gold·원문·의존성·코드·freeze 변경 금지. 상태/결과 보고 문서만 갱신한다.

**예산:** 동시 평가1개, 분석 요청최대30회, 요청당1800초·모델64호출, 전체 최대1920모델호출·관찰16시간, 제공자 자동재시도0·유료0·배포0. 1920은 이 작업의 실행 상한이며 실제 무료 잔여량 확인값이 아니다. 현재 무료 확인은 `2026-10-01T17:32:45.423911+00:00`까지만 사용한다. 한도/제공자오류/기한/무료확인 만료 시 새 호출을 중단하고 유료 대체·충전·재시작하지 않는다.

**Files:** 기존 로컬 무료 확인 JSON은 읽기 전용. 새 `E:/AgentFit/output/independent-profile-v1/runs-nvidia-diagnostics-5d75535/`에 생성 전용 결과, 이 명세 폴더에 live-result.md, 기존 STATE/ledger에 실행 핸들·관찰 기록. 이전 평가 두 폴더를 덮어쓰지 않는다.

**Interfaces:** 기존 검증된 CLI에 `--call-diagnostics --live`만 선택한다. `run_scored_process`·진단·checkpoint·중단 규칙을 그대로 사용한다.

- [ ] Step 1: 현재 Git/code freeze·실제 실행 핸들·무료 범위/만료 확인, 오프라인 CLI preflight 및 무료검증. Expected: 기존 실제 평가 terminal 상태, 동시 실행 없음,10cases/207gold, 동일 SHA, 키 미출력.
- [ ] Step 2: 같은 CLI에 env-file/access-confirmation/output을 지정해 한 번 실행한다. 같은 session handle을 관찰하며 관찰 timeout을 종료로 오해하지 않는다. Expected: 생성 전용 started/terminal, 진단 메타데이터만 저장, 개인 문서 전송 없음.
- [ ] Step 3: 정상 종료 또는 중단 시 결과 행·진단·누락·오확정·실제 호출 수·시간을 집계하고 미평가를 별도로 보고한다. unavailable은 실제0호출로 계산하지 않는다. Expected: 부분 결과를30회 성공률로 포장하지 않음, 실사용/human gold/실제Spring 미완료 유지. 결과·상태 문서만 commit/push하며 이미 검증한 코드 재리뷰는 하지 않는다.
