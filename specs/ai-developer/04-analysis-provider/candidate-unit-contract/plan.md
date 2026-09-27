# 후보 구역 계약 실험 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (native) or `superpowers:subagent-driven-development` to implement this plan task by task. Steps use `- [ ]` for tracking.

**Goal:** Solar 후보 생성의 구역 ID 중복과 정확한 인용의 구역 오배정을 opt-in 계약으로 줄일 수 있는지 평가한다.

**Architecture:** 기존 `anchored_analysis.py`와 배열 계약은 유지한다. 새 모듈이 구역 ID별 필수 키 스키마와 전 묶음 원문 위치 복원을 담당한다. 별도 평가 CLI가 기존 후보 생성과 새 계약을 같은 고정 합성 8건에서 비교하고 안전한 지표만 저장한다.

**Tech Stack:** Python 3.12 표준 라이브러리, `unittest`, 기존 Solar 전송·구역 분할 코드.

**Spec:** `specs/ai-developer/04-analysis-provider/candidate-unit-contract/spec.md`

## 전역 제약

- 기본 분석기, 공개 Profile, 최대 6회·60초, 실패 원본 7일 정책은 변경하지 않는다.
- 후보 호출은 문서당 최대 2회로 유지하며, 실제 문서·키·원본 응답은 평가 결과에 저장하지 않는다.
- 인용은 정확한 원문 문자열만 허용한다. 다른 구역으로의 이동은 그 문구가 문서 내 정확히 한 구역에서만 발견될 때만 허용한다.
- 기존 합성 8건은 튜닝 자료다. 통과해도 기본 분석기에 자동 적용하지 않는다.

## 검토 중점

- 묶음 응답의 키 누락·추가: 서버가 `ANCHORED_CANDIDATE`로 거부하는 테스트.
- 인용이 여러 구역에 존재하는데 모델이 잘못된 구역을 지정한 경우: 모호한 이동 거부 테스트.
- 같은 구역 내 같은 인용이 반복되는 경우: 현행 규칙대로 모든 위치가 후보가 되는 테스트.
- 인용이 원문 어디에도 없는 경우: 보정하지 않고 거부하는 테스트.
- 이동 후 중복과 120개 초과: 중복은 한 후보로 합치고 한도 초과는 원자적으로 실패하는 테스트.

---

### Task 1: ID별 응답 스키마와 프롬프트

**Files:** Create `ai_service/agentfit_ai/candidate_unit_contract.py`; test `ai_service/tests/test_candidate_unit_contract.py`.

**Interfaces:** `keyed_candidate_schema(batch: list[Section]) -> dict`; `KEYED_CANDIDATE_PROMPT: str`.

- [ ] **Step 1: 실패 테스트 작성.** E01 두 번째 묶음의 스키마에서 `units.properties`가 `U0004`·`U0005`·`U0006`이고 `required`가 정확히 이 세 키이며 `additionalProperties`가 false인지 확인한다. 프롬프트가 배열 출력 지시를 포함하지 않고 ID별 객체 출력을 지시하는지도 확인한다.
- [ ] **Step 2: 테스트 실패 확인.** `rtk proxy python -m unittest tests.test_candidate_unit_contract -v`를 `ai_service/`에서 실행해 새 인터페이스 부재로 실패함을 확인한다.
- [ ] **Step 3: 최소 구현.** `_object`와 현행 인용 배열의 1~2000자·최대 30개 제한을 재사용해 스키마를 만든다. 기존 프롬프트의 인용 규칙은 보존하고 출력 모양만 교체한다.
- [ ] **Step 4: 해당 테스트 통과 확인.** 같은 명령을 실행한다.

### Task 2: 모든 묶음의 원자적 원문 위치 복원

**Files:** Modify `ai_service/agentfit_ai/candidate_unit_contract.py`; test `ai_service/tests/test_candidate_unit_contract.py`.

**Interfaces:** `normalize_keyed_candidates(replies: list[dict], batches: list[list[Section]], source_units: list[Section]) -> tuple[list[dict], dict]`. 반환 후보는 현행 `candidate_views`가 받는 `id`, `unitId`, `quote`, `span` 형식이다. 지표는 `remapped`, `deduplicated` 정수다. 실패는 `AnalysisError` 코드 `ANCHORED_CANDIDATE`와 안전한 `candidate_detail.reason`을 사용하고, 120개 초과는 `SECTION_LIMIT`를 사용한다.

- [ ] **Step 1: 실패 테스트 작성.** ID 키 누락·추가, E03/E04의 다른 구역 인용, 모호한 중복 인용, 원문 밖 인용, 동일 구역 반복 등장, 이동 후 중복, 120개 초과, 둘째 묶음 실패 시 부분 결과 없음, `candidate_views(..., focus=True)` 호환을 각각 검증한다.
- [ ] **Step 2: 실패 확인.** `rtk proxy python -m unittest tests.test_candidate_unit_contract -v`.
- [ ] **Step 3: 최소 구현.** 먼저 모든 응답의 구조와 인용을 검증하고, 원문 구역을 확정한 뒤 `(unitId, quote)` 기준으로 중복을 제거한다. 모든 일치 위치를 펼쳐 span 순서로 정렬한 후 F0001부터 ID를 부여한다. 유사 문자열 보정은 하지 않는다.
- [ ] **Step 4: 해당 테스트 통과 확인.** 같은 명령을 실행한다.

### Task 3: 안전한 교차 비교 CLI

**Files:** Create `ai_service/agentfit_ai/candidate_unit_evaluation.py`; test `ai_service/tests/test_candidate_unit_evaluation.py`.

**Interfaces:** `new_candidate_recall(case: dict, key: str) -> dict`; CLI `python -m agentfit_ai.candidate_unit_evaluation --live --output <new-directory>`.

- [ ] **Step 1: 실패 테스트 작성.** 두 묶음만 호출하는 가짜 전송으로 성공·첫/둘째 묶음 실패·실제 호출 수를 검증한다. 출력 JSON에 문서·키·인용·원본 응답이 없고 지표만 있음을 확인한다. `--live` 없는 실행은 API를 호출하지 않아야 한다.
- [ ] **Step 2: 실패 확인.** `rtk proxy python -m unittest tests.test_candidate_unit_evaluation -v`.
- [ ] **Step 3: 최소 구현.** `embedding_section_evaluation.load_cases`, `gold_spans`, `candidate_recall`을 재사용한다. 새 계약은 현행과 동일한 Solar 모델·입력 문맥·토큰 설정을 사용한다. 문서별로 기존/신규 호출 순서를 교대로 바꾸고 각 팔의 유효성·금 span 회수·오류 종류·호출 수·지연을 기록한다. 원본 응답은 메모리에서 검증 후 버린다.
- [ ] **Step 4: 해당 테스트 통과 확인.** 같은 명령을 실행한다.

### Task 4: 고정 실행·판정·브랜치 검증

**Files:** Create `specs/ai-developer/04-analysis-provider/candidate-unit-contract/results/run1/{plan,results}.json`, `validation.md`; update `tasks.md`.

- [ ] **Step 1: 고정 실행.** 새 출력 폴더에 합성 8건의 현행/신규 교차 비교를 한 번 실행한다. 실행 전 데이터 해시, 모델, 순서, 관문을 `plan.json`에 기록한다.
- [ ] **Step 2: 판정 기록.** 명세의 8/8·27/27·원문 오류 0·호출 2회 관문과 지연을 그대로 적용한다. 미달이면 추가 튜닝 없이 실패로 기록하고 기본 분석기에 적용하지 않는다.
- [ ] **Step 3: 전체 검증.** `rtk proxy python -m unittest discover -s tests -q`를 `ai_service/`에서 실행하고, `git diff --check` 및 결과 파일의 비밀 값·원본 데이터 검사를 수행한다.
- [ ] **Step 4: 독립 검토 후 커밋·push.** `feature/candidate-unit-contract`에 이번 기능 파일만 커밋하고 원격 동기화를 확인한다. 무관한 untracked 파일은 보존한다.
