# NVIDIA 단독 후보 분석 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. 사용자가 선택한 직접 구현, 목표의 설계/계획 자율 승인 적용.

**Goal:** Solar 키 없이 실행 가능한 선택형 내부 NVIDIA 분석 경로를 제공한다.
**Architecture:** 기존 LangExtract/후보 분류 sender 선택 → 공통 pipeline에 명시적 후보 모델 → NVIDIA 전용 진입 함수. 서버/API 모드는 후속 연결.
**Tech Stack:** Python3.13, unittest, LangExtract1.7.0, 기존 NVIDIA SSE/parser.
**Spec:** specs/ai-developer/nvidia-only-candidates/spec.md

## Global Constraints

- feature/nvidia-only-candidates, base c0b3d2297738a919c78ce5ab82bc6db8cd3715b2. 기존 독립 analysis-failure-stages worktree 재사용.
- 공개 API/Profile/v2/기본 혼합 pipeline·평가 기준선 불변. 추가 의존성0, 실제 외부 호출0/유료0원, 자동 재시도0. 사용자 무료 한도 검증 전 실제 평가 금지.
- 작업45분 점검/suite180초. 기본 전용 경로 최대64호출, 모델당 기존600초 transport 인자. 전체 wall timeout은 후속 worker/runner 경계의 책임이며 이번 동기 내부 함수의 기능이 아니다.

## Review Focus

1. NVIDIA 선택인데 기본 transport가 Solar endpoint를 호출하는가 — 선택 모델 payload와 금지 Solar sentinel 검증.
2. 키 누락/잘못된 모델이 SDK 일부 실행 후 발견되는가 — 모든 입력 사전 차단 테스트.
3. SDK가 429/503를 잡고 재시도하거나 결과를 반환하는가 — 실패 latch와 후속 전송0·단계 실패 검증.
4. NVIDIA 응답 모델을 Solar로 바꿔 검증을 우회하는가 — 실제 반환 model 엄격 일치 및 양 단계 불일치 테스트.
5. 새 함수가 기존 baseline과 같은 것으로 오인되는가 — 명시적 전용 함수/추적 모델·provider 검사/문서 한계 및 기존 전체 gate.

### Task 1: 선택형 NVIDIA sender와 단독 파이프라인

**Files:** Modify ai_service/agentfit_ai/langextract_solar_trial.py, candidate_first_profile.py, candidate_analysis_pipeline.py; Create ai_service/tests/test_nvidia_only_candidates.py; Create ai_service/runtime_tests/test_nvidia_only_runtime.py; Create specs/ai-developer/nvidia-only-candidates/validation.md, work/harness/nvidia-only-candidates/STATE.md.
**Interfaces:** `extract_candidates(..., transport=None, ..., nvidia_model=None)`와 `classify_profile_candidates(..., transport=None, ..., nvidia_model=None)`은 기본 Solar를 유지한다. NVIDIA 지정 시 lazy import한 NvidiaAnalyzer/streaming sender를 사용한다. `analyze_integrated_candidates(..., candidate_model=None)`과 명세의 `analyze_nvidia_candidates`를 제공한다. wrapper는 후보모델을 명시하고 solar_key=None/retry0을 고정한다.

- [ ] Step1: 새 unit 테스트에 한 키 전체 분석·세 모델 선택·금지 Solar·실패 latch·잘못된 조합 사전 거부·공동 예산을 작성한다. runtime 테스트에 실제 SDK 성공/v2와 두 단계 모델 불일치를 작성한다. Run: `python -m unittest discover -s tests -p test_nvidia_only_candidates.py` 및 runtime 동일 파일. Expected: 전용 진입 함수 부재로 실패, 외부 연결0.
- [ ] Step2: 두 sender를 선택형으로 확장하고 공통 pipeline의 NVIDIA 선택 검증·키 라우팅·meter 중단 latch를 구현한다. 기존 기본값과 Solar 응답 검증을 유지한다. Expected: 전용 사례 통과, payload model/keys/근거 결과 일치.
- [ ] Step3: 로컬 SDK 테스트와 전체 unit/runtime/contract/core-flow를 각180초 상한으로 실행한다. Expected: 전부 통과, 원래 baseline과 HTTP/worker 변경 없음. validation/STATE 기록하고 commit/task-done 실행.
- [ ] Step4: 전체 독립 리뷰1회, Critical/Important는 실패 회귀부터1수정pass. feature push와 정확한 커밋 CI 확인. Expected: 로컬 구현/모델 미평가를 구분한 최종 보고. 사용자 요청에 따라 작업 폴더 보존.

## 자기 검토

단일 작업으로 sender 선택과 공통 meter 인터페이스를 함께 구현한다. 기존 테스트를 삭제하거나 품질 기준을 낮추지 않는다. 옵션 조합이 복잡해지지 않도록 wrapper가 안전한 고정값을 제공하며 기존 호출 signature를 보존한다.
