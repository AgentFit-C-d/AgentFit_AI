# NVIDIA Review Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자가 승인한 직접 자율 실행, 구현자 에이전트 없음, 최종 독립 리뷰1회.

**Goal:** 관측된 GLM 검토 실패를 비교할 선택형 DeepSeek 검토 경로를 노출한다.
**Architecture:** 기존 파이프라인 옵션을 자식 packet과 평가 설정에 연결한다. 기본 경로는 유지하고 명시적 진단 평가만 별도freeze/variant로 기록한다.
**Tech Stack:** Python3.13/unittest/asyncio/기존 LangExtract·NVIDIA streaming, 추가 의존성 없음.
**Spec:** specs/ai-developer/nvidia-review-model-routing/spec.md

## Global Constraints

- feature/nvidia-review-model-routing, base29893eb. 기존 격리 작업 폴더 재사용, 완료한 실험 코드는Git 기준 커밋으로 보존하며 결과/gold/이전freeze는 수정하지 않는다.
- 공개 API/기본 모델/프롬프트/scorer/64호출/1800초/자동재시도0/무료 정책 유지. 구현 외부0/유료0/배포0.
- 합성30초·대상120초·suite180초·CI10분·구현60분마다 상태 점검. 실제 실행은 후속 별도 예산 필요.

## Review Focus

1. 진단/모드가 없는 모델 선택, 임의 타입/모델 문자열이 키나 자식 호출까지 도달하는가 — Task1/2 negative tests.
2. 선택 옵션이 한 경계에서 사라져 GLM을 호출하고도 DeepSeek 비교로 기록하는가 — Task1 실제SDK/worker 전달 및 Task2 모델 불일치 행 거절.
3. 기본 packet/variant/CLI가 선택 옵션 때문에 바뀌는가 — Task1 기본 인자 불변, Task2 기존 tests 회귀.
4. 실패 후 재실행이나 다른 모델의 폴더를 재개하는가 — Task2 manifest/failure-latch negative tests.
5. 모델 변경이 다른 추출·분류·기능 호출·점수·재시도 예산도 바꾸는가 — Task2 loopback 실제 모델열/점수/503 중단 비교.

### Task 1: 선택 모델을 자식 분석 경계에 전달

**Files:** Modify ai_service/agentfit_ai/{analysis_process,analysis_worker,candidate_service_worker}.py; Create ai_service/tests/test_nvidia_review_model_routing.py.
**Interfaces:** run_analysis_process(...,nvidia_review_model=None), execute_nvidia_analysis(...,review_model=None); internal request reviewModel. 허용 두 모델은 기존 analysis_call_metadata.MODELS를 사용. 명시 선택은 nvidia_only=True/call_diagnostics={}에서만 허용.

- [ ] Step1: 새 테스트 `ParentReviewRoutingTests`/`WorkerReviewRoutingTests` 작성. 선택 문자열의 정확한 전달, 기본 키 집합 불변, unknown/type/다른mode/진단없음 거절 및 no-spawn, 잘못된 검토 모델 trace 거절. `python -m unittest tests.test_nvidia_review_model_routing -v` 실행; Expected: 옵션 없음 또는 전달 누락 RED.
- [ ] Step2: 위 세 경계에 선택 인자 전달·엄격 검증만 구현. 명시 선택의 trace는 coverage에선 선택 모델, 다른 호출에선 DeepSeek인지 검증하고 채택. Expected: 새 모듈과 기존 진단/프로세스 테스트 GREEN.
- [ ] Step3: 변경 범위 확인·commit·task-done으로 관련 단위 모듈 실행. Expected: 새 전달 계약이 동작하며 기본 서비스 요청은 그대로.

### Task 2: 별도 비교 평가 등록과 실제 자식 검증

**Files:** Modify ai_service/agentfit_ai/{nvidia_evaluation_inputs,nvidia_evaluation_runner}.py; Create ai_service/tests/test_nvidia_review_evaluation.py, ai_service/runtime_tests/test_nvidia_review_routing_runtime.py; Create specfolder/{freeze.json,validation.md,review.md}; Modify README.md.
**Interfaces:** build_freeze/prepare_evaluation(...,call_diagnostics=False,review_model=None); run_scored_process(...,call_diagnostics=None,review_model=None); CLI --review-model {two allowed models} only with --call-diagnostics. _refresh rebuilds selection from validated variant; _diagnostic_row(...,review_model='z-ai/glm-5.3') checks stage/model correspondence; evaluate uses selected strict validator. ExplicitGLM retains existing diagnostic variant; DeepSeek gives nvidia-deepseek-review-v1.

- [ ] Step1: RED new preflight/CLI/typed-row tests for distinct variant and model, missing diagnostics/unsupported model rejection before key access, default/explicitGLM equivalence, model/freeze/manifest mismatch, successful and failed checkpoint model spoofing, failure replay block. Expected: missing selection option RED.
- [ ] Step2: Implement opt-in settings/variant/freezer/runner/CLI propagation with unchanged public score. Expected: new+legacy evaluation tests GREEN.
- [ ] Step3: Real SDK/child/loopback compare default and selected same score,5calls, expected requested-model sequence. Verify selected review503 and429 without retry, wrong returned model rejection and timeout/cancel existing behavior. `python -m unittest discover -s runtime_tests -p test_nvidia_review_routing_runtime.py -v`; Expected: selected review uses DeepSeek and no other stage change.
- [ ] Step4: Generate new freeze offline only after final code, preserve previous evidence hashes, run actual CLI preflight10/207 with new selection, write usage/validation. Commit; task-done runs tests/runtime/contract/core each180sec. Expected: all pass with known platform skips, no external calls.
- [ ] Step5: Single fresh final reviewer; regrade all findings, Important/Critical one RED→GREEN fix pass + whole gate, minor ledger only, no re-review. Feature push and exact-code CI. Expected: implementation readiness only; no real accuracy claim.

## 자기 검토

Task1의 선택 인자와 모델 일치 검증을 Task2가 소비한다. CLI는기본None을 유지하며 구형 메타데이터에 새 키를 추가하지 않는다. 기존MODELS두개와 실제 사용자 무료범위가 같다. 주요 공개 계약 변경과 모델 품질 보장을 포함하지 않는다.
