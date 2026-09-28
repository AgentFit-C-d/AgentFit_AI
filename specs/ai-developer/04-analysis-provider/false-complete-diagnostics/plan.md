# False Complete Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 단일 분석 실행에서 감지된 오확정의 최초 관측 불일치 단계와 의미 검토 감지 여부를 안전한 메타데이터로 보고한다.

**Architecture:** 기존 분석기의 no-op 관측 경계에 후보 풀 훅 하나를 더하고, 평가 전용 하위 클래스가 호출 단위 후보·Profile·검토 이슈를 메모리에만 모은다. 순수 판정기가 합성 정답 및 별도 근거 주석과 대조하고, 별도 CLI가 20건을 한 번씩 실행해 비밀 값 없는 결과를 쓴다.

**Tech Stack:** Python 표준 라이브러리, 기존 `unittest`, `agentfit_ai`의 `AnchoredAnalyzer`·`RecoverableAnchoredAnalyzer`·합성 평가 도구. 새 의존성 없음.

**Python:** `C:/Users/fhtkr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` (`rtk proxy`로 실행).

**Spec:** `specs/ai-developer/04-analysis-provider/false-complete-diagnostics/spec.md`

## Global Constraints

- 기존 `analyze()`·`analyze_recoverable()` 반환, 공개 Profile, Spring/API/DB 계약 변경 없음. 진단은 opt-in이며 분석 결과를 수정하지 않는다.
- 사례당 분석 1회, 추가 제공자 호출 0회, 최대 6회·설정상 60초 기한 유지. 관측 60초 초과는 보고한다.
- 파일 산출물에 원문·인용문·추출값·원본 응답·프롬프트·API 키·Profile 전체를 기록하지 않는다. 기존 실패 원본 7일 정책 유지.
- `first_observed_divergence`는 `candidate_gap`·`judgment_mismatch`·`repair_regression`·`undetermined` 중 하나다. 인과 원인으로 표현하지 않는다.
- `review_detected`는 `true`·`false`·`null`이다. 의미 근거의 구조 검증을 정답 검증으로 간주하지 않는다.
- 이전 run3의 `Q-001`·`N-004` 오확정을 새 실행의 원인으로 소급하지 않는다.

## Review Focus

- 동일 분석기 인스턴스의 연속·동시 호출에서 후보와 Profile이 서로 섞이지 않는다. Task 1 테스트.
- 복구형 `needs_confirmation`에서 마지막 유효 초안이 있어도 오확정으로 집계하지 않는다. Task 2·3 테스트.
- 금지 문자열이 여러 필드에 나타나 필드를 특정할 수 없으면 `undetermined`로 남긴다. Task 2 테스트.
- 근거 문구가 중복되거나 주석의 원문 구간이 맞지 않으면 후보 누락을 단정하지 않는다. Task 2 테스트.
- 의미 검토가 실패하거나 재검토가 수행되지 않으면 `review_detected=null`이며 분석의 원래 오류를 보존한다. Task 1·2 테스트.

---

### Task 1: 한 호출의 관측 경계

**Files:**
- Modify: `ai_service/agentfit_ai/anchored_analysis.py` (`_analyze`의 후보 정규화 직후)
- Create: `ai_service/agentfit_ai/false_complete_observation.py`
- Test: `ai_service/tests/test_false_complete_observation.py`

**Interfaces:**
- `AnchoredAnalyzer._observe_candidate_pool(pool: list[dict]) -> None`: 기본 no-op. 후보 ID가 정해진 뒤 판단 요청 전에 한 번 호출한다. 기존 `_observe_profile(stage, profile)`와 `_observe_review_issues(stage, issues)`를 재사용한다.
- `ObservedRecoverableAnalyzer(RecoverableAnchoredAnalyzer).analyze_observed(document: str, document_id: str) -> tuple[dict, dict]`: 첫 값은 기존 복구형 결과, 둘째 값은 평가기 내부에서만 쓰는 `{"candidates": [{"id", "start", "end"}], "profiles": [(stage, profile)], "reviews": [(stage, issues)]}`. Profile 참조는 호출 종료 뒤 평가기가 버린다.

- [ ] **Step 1: 실패 테스트 작성.** `test_candidate_hook_runs_once_before_judgment`, `test_observed_result_equals_recoverable_result`, `test_review_and_recheck_stages_are_distinct`, `test_context_resets_after_error_and_isolates_calls`를 작성한다. 가짜 제공자에서 호출 수·최종 결과가 기존과 같고 후보에는 인용문이 없음을 확인한다.
- [ ] **Step 2: 실패 확인.** `rtk proxy C:/Users/fhtkr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest tests.test_false_complete_observation -v`를 `ai_service`에서 실행해 신규 메서드 부재로 실패하는지 본다.
- [ ] **Step 3: 최소 구현.** `anchored_analysis.py`에 no-op 훅과 정규화 직후 호출을 추가한다. 하위 클래스는 `ContextVar`와 `finally`를 써서 호출 단위 상태를 해제하고, 기존 복구형 훅을 `super()`로 반드시 호출한다.
- [ ] **Step 4: 통과 확인.** 신규 테스트와 `tests.test_recoverable_analysis`, `tests.test_recoverable_checkpoints`를 실행한다.
- [ ] **Step 5: 커밋.** Task 1의 코드·테스트만 `feat: observe false complete checkpoints`로 기록한다.

### Task 2: 정답 근거 주석과 순수 단계 판정

**Files:**
- Create: `specs/ai-developer/04-analysis-provider/false-complete-diagnostics/gold-evidence.json`
- Create: `ai_service/agentfit_ai/false_complete_scoring.py`
- Test: `ai_service/tests/test_false_complete_scoring.py`

**Interfaces:**
- `load_gold_evidence(cases: list[dict]) -> dict[str, dict[str, list[tuple[int, int]]]]`: `Q-001`의 두 기능과 `N-004`의 확정 AI에 대해 원문에서 하나로 특정되는 근거 구간을 검증해 반환한다. 기존 focus 사례는 `gold_spans(case)`의 구역·인용 주석을 사용한다. 원문이나 인용문을 결과에 복사하지 않는다.
- `diagnose_case(case: dict, result: dict, observation: dict, gold_evidence: dict) -> list[dict]`: 기존 full/focus 채점에서 `complete`로 잘못 확정된 필드만 `{field, first_observed_divergence, review_detected, candidate_ids, evidence_spans}` 형태의 안전한 행으로 반환한다. 원본 Profile·값·인용문은 반환하지 않는다.

- [ ] **Step 1: 실패 테스트 작성.** 후보 없는 필수 구간 → `candidate_gap`, 후보가 있으나 첫 판단 오답 → `judgment_mismatch`, 첫 판단 정답·수정 오답 → `repair_regression`, 모호한 주석·중복 필드 → `undetermined`를 고정 입력으로 검증한다. `review_detected` 세 값, focus 금지 문자열, `needs_confirmation` 제외도 검증한다.
- [ ] **Step 2: 실패 확인.** `rtk proxy C:/Users/fhtkr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest tests.test_false_complete_scoring -v`를 `ai_service`에서 실행한다.
- [ ] **Step 3: 최소 구현.** 기존 `score_profile`, `full_score`, `focus_score`, `gold_spans`의 뜻을 재사용한다. 근거 구간은 후보 `start <= gold.start` 및 `end >= gold.end`일 때 포괄된다. 서로 다른 정답 항목에는 서로 다른 후보가 필요한지 일대일 최대 대응으로 확인한다. 필드 매핑 또는 단계 자료가 불충분하면 `undetermined`; 검토 완료 이슈에 필드가 있으면 `true`, 완료·무이슈면 `false`, 미완료면 `null`이다.
- [ ] **Step 4: 통과 확인.** 신규 테스트와 `tests.test_keyed_profile_evaluation`을 실행한다.
- [ ] **Step 5: 커밋.** Task 2의 주석·코드·테스트만 `feat: classify observed false completions`로 기록한다.

### Task 3: 안전한 단일 실행 평가기

**Files:**
- Create: `ai_service/agentfit_ai/false_complete_evaluation.py`
- Test: `ai_service/tests/test_false_complete_evaluation.py`

**Interfaces:**
- `run_case(case: dict, key: str, *, provider=post_solar, analyzer_factory=ObservedRecoverableAnalyzer, clock=time.monotonic) -> dict`: 기존 `recoverable_draft_evaluation.options()`로 한 번 분석하고 Task 2의 안전한 진단 행을 결합한다.
- `aggregate(rows: list[dict], *, planned: int = 20) -> dict`: 전체 20건 분모, 상태별 건수, 오확정·단계·검토 감지·`undetermined`, 최대 호출·60초 관측 초과를 집계한다.
- CLI: `python -m agentfit_ai.false_complete_evaluation --live --env-file <local .env> --output <new directory>`; 계획·결과·요약 JSON에 자료·코드 SHA-256과 안전한 수치만 기록한다.

- [ ] **Step 1: 실패 테스트 작성.** 동일 사례 제공자 호출은 한 분석 분량만 발생하고 기존 복구 결과가 그대로임을 확인한다. 실패·제안·정상 성공·오확정의 분모, 6회/60초 위반, 중첩 산출물 금지 키·원문 비노출, 파일 작성 실패 시 원본 비기록을 검증한다.
- [ ] **Step 2: 실패 확인.** `rtk proxy C:/Users/fhtkr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest tests.test_false_complete_evaluation -v`를 `ai_service`에서 실행한다.
- [ ] **Step 3: 최소 구현.** `load_profile_cases`, 기존 옵션·키 로더·안전 JSON 작성기를 재사용한다. 메모리 관측치는 판정 직후 버리고, 진단 실패는 안전 코드와 `undetermined`로 남기되 분석 상태를 바꾸지 않는다.
- [ ] **Step 4: 통과 확인.** 신규 테스트와 `tests.test_recoverable_draft_evaluation`, 전체 `rtk proxy C:/Users/fhtkr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest discover -s tests`를 `ai_service`에서 실행한다. 저장소 루트에서 `rtk proxy git diff --check`도 확인한다.
- [ ] **Step 5: 커밋.** Task 3의 코드·테스트만 `feat: evaluate false complete stages safely`로 기록한다.

### Task 4: 합성 20건 실행과 판정 기록

**Files:**
- Create: `specs/ai-developer/04-analysis-provider/false-complete-diagnostics/validation.md`
- Create: `specs/ai-developer/04-analysis-provider/false-complete-diagnostics/results/run1/` (안전한 JSON만)

**Interfaces:**
- Task 3 CLI의 기존 합성 20건을 사례당 한 번 실행한다. 결과는 이전 run3와 인과·개선량 비교에 사용하지 않는다.

- [ ] **Step 1: 실행 전 고정 확인.** 합성 자료 20건, 코드·자료 SHA-256, 로컬 `.env` 키 존재 여부만 확인하고 키 값은 출력하지 않는다.
- [ ] **Step 2: 라이브 평가.** `rtk proxy C:/Users/fhtkr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m agentfit_ai.false_complete_evaluation --live --env-file E:/AgentFit/.env --output ../specs/ai-developer/04-analysis-provider/false-complete-diagnostics/results/run1`을 `ai_service`에서 실행한다. 종료 코드가 실패여도 결과·오류·시간 초과를 보존한다.
- [ ] **Step 3: 산출물·결과 검증.** JSON의 금지 키·원문·인용문·키 비노출과 20건 분모·사례당 1분석·호출 상한을 확인한다. `Q-001`·`N-004`가 재현되지 않으면 재현 안 됨과 판정 한계를 명시한다.
- [ ] **Step 4: 검증 문서와 최종 커밋·push.** 관측된 단계별 건수, `undetermined`, 검토 누락, 60초 초과, 미평가 의미 근거를 구분해 기록한다. 변경 전체를 검토하고 `feature/false-complete-diagnostics`를 push한다.
