# Recoverable Analysis Draft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실패한 분석에서 검증 가능한 값은 사용자 확인 전 제안으로 남기고, 판단할 수 없는 필드는 질문 대상으로 분리하는 선택형 AI 내부 결과를 만든다.

**Architecture:** 기존 `AnchoredAnalyzer`에 기본 동작이 없는 관측 훅을 추가하고, 별도 `RecoverableAnchoredAnalyzer`가 한 번의 분석에서 마지막 유효 초안·검토 이슈·판단 실패를 메모리에만 잡는다. 순수 변환 함수가 필드별 보존·격하와 질문 ID를 계산한다. 기존 `analyze()`는 그대로이고 새 `analyze_recoverable()`만 결과 상태를 반환한다.

**Tech Stack:** Python 표준 라이브러리, 기존 `unittest`, `agentfit_ai`의 Profile·AnchoredAnalyzer·안전 진단 함수. 새 의존성 없음.

**Spec:** `specs/ai-developer/04-analysis-provider/recoverable-analysis-draft/spec.md`

## Global Constraints

- 기본 `analyze()`·기존 성공 Profile JSON·Spring/API/DB 계약 변경 없음.
- `complete`만 기존 분석 성공이다. `needs_confirmation`은 저장 완료가 아니고 모든 값이 사용자 확인 전 제안이다.
- `null`과 `[]`의 기존 뜻을 유지하고, 실패 때문에 비운 `null`은 별도 `unresolved` 상태로 구분한다.
- 추가 제공자 호출 0회, 기존 최대 6회·60초 예산 유지. 관측 지연 초과를 숨기지 않는다.
- 원문·원본 응답·API 키를 복구형 결과나 평가 산출물에 기록하지 않는다. 기존 실패 건 원본 7일 정책 유지.
- 모든 실험은 선택형이다. 기본값·운영 모델 자동 승격 없음.

## Review Focus

- 입력에 API 키가 포함되면 초안이 있어도 복구형 결과를 만들지 않고 기존 민감 입력 오류를 유지한다. Task 4 테스트.
- 판단 응답의 키·ID가 깨지면 정상처럼 일부 필드를 주워 담지 않고 실패한다. Task 2 테스트.
- 명시적 부재 `[]`와 근거는 제안에서 유지되지만 미정 `null`을 `[]`로 바꾸지 않는다. Task 1·2 테스트.
- 같은 인용이 반복되거나 근거가 모호하면 원문 위치를 추측하지 않는다. Task 2 테스트.
- 초안 이전 시간 초과는 실패, 검토 중 시간 초과는 전 필드 미검토 상태로 표시한다. Task 4 테스트.

---

### Task 1: 복구형 결과의 순수 투영

**Files:**
- Create: `ai_service/agentfit_ai/recoverable_draft.py`
- Test: `ai_service/tests/test_recoverable_draft.py`

**Interfaces:**
- Produces: `project_draft(document: str, document_id: str, profile: dict, *, unresolved: dict[str, str], review_complete: bool, error_code: str) -> dict`.
- Output keys: `outcome`, `profile`, `fieldStates`, `questions`, `error`. `fieldStates`는 10개 필드 각각 `suggested`, `unknown`, `unresolved` 중 하나다. `questions`는 `{field, reason, questionId}`의 중복 없는 배열이며 `questionId`는 `confirm_<field>`로 고정한다.

- [ ] **Step 1: 실패 테스트 작성.** 정상 값·`[]`·`null`, 이슈 필드 격하, 원문·키 문자열 비노출, 필드별 질문 중복 제거를 각각 검증한다. `review_complete=False`이면 값은 제안, 모든 `null`은 `unresolved`임을 확인한다.
- [ ] **Step 2: 테스트 실행.** `rtk proxy <python> -m unittest tests.test_recoverable_draft`; 신규 함수 미구현으로 실패해야 한다.
- [ ] **Step 3: 최소 구현.** `validate_profile`로 격하 후 Profile을 다시 검사한다. 허용된 필드·사유 코드만 결과에 남긴다. 복구 결과를 `complete`로 만들지 않는다.
- [ ] **Step 4: 관련 테스트 실행.** 신규 테스트와 `tests.test_profile` 통과를 확인한다.
- [ ] **Step 5: Task 1 파일만 커밋.** 메시지 `feat: project safe recoverable draft states`.

### Task 2: 판단 실패의 필드별 안전한 재구성

**Files:**
- Create: `ai_service/agentfit_ai/recoverable_judgment.py`
- Test: `ai_service/tests/test_recoverable_judgment.py`

**Interfaces:**
- Produces: `salvage_judgment(document: str, document_id: str, pool: list[dict], reply: dict) -> tuple[dict | None, dict[str, str]]`.
- 첫 값은 `validate_profile`을 통과한 제안 초안 또는 `None`; 두 번째는 안전한 필드별 사유 코드다. 후보별 판단 키·ID가 온전하지 않으면 `None`을 반환한다.

- [ ] **Step 1: 실패 테스트 작성.** 한 필드의 `selected+tentative`와 다른 필드의 정상 선택이 함께 있을 때 정상 필드만 보존한다. 충돌·잘못된 역할·명시적 부재는 각 필드를 독립 검증한다. 키/ID 누락, 모호한 인용, 모든 필드 실패 시 `None`을 확인한다.
- [ ] **Step 2: 테스트 실행.** `rtk proxy <python> -m unittest tests.test_recoverable_judgment`; 신규 함수 미구현으로 실패해야 한다.
- [ ] **Step 3: 최소 구현.** 전체 판단 응답의 기본 형태·ID 범위를 먼저 검사한 다음 필드별 선택만 남겨 기존 `classify()`·`validate_profile()`를 재사용한다. 실패한 필드는 `null`/근거 없음으로 격하하고 값·근거를 임의 보정하지 않는다.
- [ ] **Step 4: 관련 테스트 실행.** 신규 테스트와 `tests.test_selected_decision_constraints`, `tests.test_merge_diagnostics` 통과를 확인한다.
- [ ] **Step 5: Task 2 파일만 커밋.** 메시지 `feat: salvage independently valid judgment fields`.

### Task 3: 분석 경계의 메모리 관측 훅

**Files:**
- Modify: `ai_service/agentfit_ai/anchored_analysis.py` (`_analyze`의 판단·초안·검토 경계)
- Test: `ai_service/tests/test_recoverable_checkpoints.py`

**Interfaces:**
- Produces: 기본 no-op 메서드 `_observe_judgment_failure(reply, pool, document, document_id, error)`, `_observe_profile(stage, profile)`, `_observe_review_issues(stage, issues)`. 복구형 subclass가 override한다.
- `analyze()`의 반환·예외·호출 순서는 바꾸지 않는다.

- [ ] **Step 1: 실패 테스트 작성.** 기존 mock transport로 판단 검증 실패·초안 생성·의미 수정·재검토 이슈의 훅 시점과 인자를 확인한다. 기본 분석 결과와 제공자 호출 수가 기존과 동일함을 비교한다.
- [ ] **Step 2: 테스트 실행.** `rtk proxy <python> -m unittest tests.test_recoverable_checkpoints`; 훅 부재로 실패해야 한다.
- [ ] **Step 3: 최소 구현.** 판단 merge 예외 직전, 유효 Profile 완성 직후, 리뷰 이슈 검증 직후에만 훅을 호출한다. 진단 dict에는 원문·초안·원본 응답을 넣지 않는다.
- [ ] **Step 4: 관련 테스트 실행.** 신규 테스트와 `tests.test_semantic_review`, `tests.test_anchored_candidates` 통과를 확인한다.
- [ ] **Step 5: Task 3 파일만 커밋.** 메시지 `feat: observe anchored analysis checkpoints`.

### Task 4: 선택형 분석 진입점과 실패 매핑

**Files:**
- Create: `ai_service/agentfit_ai/recoverable_analysis.py`
- Test: `ai_service/tests/test_recoverable_analysis.py`

**Interfaces:**
- Produces: `RecoverableAnchoredAnalyzer(AnchoredAnalyzer).analyze_recoverable(document: str, document_id: str) -> dict`.
- `complete`에는 기존 성공 Profile, `needs_confirmation`에는 Task 1 투영, `failed`에는 안전한 오류 코드만 둔다. 판단 실패는 Task 2를 사용한다.

- [ ] **Step 1: 실패 테스트 작성.** 후보 실패는 `failed`; 판단 상태 오류는 정상 필드만 `needs_confirmation`; `ANCHORED_MISSING_CANDIDATE`와 반복 `overbroad`는 지적 필드 격하; 리뷰 형식 오류·시간 초과는 미검토 상태; 정상 성공은 기존 결과와 동일함을 검증한다. 민감 입력, 초안 전 시간 초과, 연속 호출 간 상태 오염도 테스트한다.
- [ ] **Step 2: 테스트 실행.** `rtk proxy <python> -m unittest tests.test_recoverable_analysis`; 신규 진입점 미구현으로 실패해야 한다.
- [ ] **Step 3: 최소 구현.** 단일 호출에서만 유효한 스냅샷을 메모리에 유지한다. `super().analyze()`의 성공/실패 뒤 Task 1·2를 호출하고 `finally`에서 스냅샷을 버린다. 실패 원본 보관은 기존 경로에 맡긴다.
- [ ] **Step 4: 관련 테스트 실행.** 신규 테스트와 기존 `tests.test_evidence_pipeline`, `tests.test_call_diagnostics` 통과를 확인한다.
- [ ] **Step 5: Task 4 파일만 커밋.** 메시지 `feat: expose opt-in recoverable analysis outcome`.

### Task 5: 같은 실행에서 안전성과 유용성 평가

**Files:**
- Create: `ai_service/agentfit_ai/recoverable_draft_evaluation.py`
- Test: `ai_service/tests/test_recoverable_draft_evaluation.py`
- Create after live run: `specs/ai-developer/04-analysis-provider/recoverable-analysis-draft/validation.md` and safe `results/run1/`.

**Interfaces:**
- Evaluator receives the same 20 synthetic cases used in the prior paired comparison. Each case calls `analyze_recoverable()` once; its `complete`/`failed` branch gives the simultaneous old outcome, with no independent provider rerun.

- [ ] **Step 1: 실패 테스트 작성.** 동일 실행 1회만 호출, 실패 분모 고정, 정답 제안·오제안·질문 수·오확정·호출 수·관측 지연 집계, 결과 파일의 원문·키·원본 응답 비기록을 검증한다.
- [ ] **Step 2: 테스트 실행.** `rtk proxy <python> -m unittest tests.test_recoverable_draft_evaluation`; 평가기 미구현으로 실패해야 한다.
- [ ] **Step 3: 최소 구현.** 기존 `load_profile_cases`, `full_score`/`focus_score`, 안전 진단을 사용한다. 실행 계획에 코드·자료 SHA-256을 기록하고 실패 포함 고정 분모로 집계한다.
- [ ] **Step 4: 전체 테스트 실행.** `rtk proxy <python> -m unittest discover -s tests`; 신규·기존 테스트 모두 통과해야 한다. `git diff --check`도 실행한다.
- [ ] **Step 5: 합성 20건 라이브 평가 실행.** 로컬 `.env`의 키를 메모리로만 읽고 6회·60초/원문 비기록 관문과 정답 제안·오제안·질문 부담을 기록한다. 실패 결과도 숨기지 않는다.
- [ ] **Step 6: 검증 문서·상태 기록 후 커밋·push.** 결과를 기본값 승격과 구분한다. 원래 작업 폴더의 사용자 변경을 보존한다.
