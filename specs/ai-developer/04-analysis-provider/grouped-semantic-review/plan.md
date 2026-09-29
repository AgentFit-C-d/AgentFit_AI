# Grouped Semantic Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 원문 선택자 분석의 의미 검토를 3개 필드 묶음으로 나누고, 모두 검증되기 전에는 자동 완료하지 않는다.

**Architecture:** 기본 `SolarAnalyzer`에는 기본값이 현재 단일 검토인 내부 묶음 훅을 둔다. opt-in `SourceSelectorSolarAnalyzer`만 묶음별 짧은 검토 요청과 서버 정규화를 사용한다. 의미 이슈가 있으면 수정 호출 없이 복구 초안의 확인 필요 상태로 반환한다.

**Tech Stack:** Python 3.13, 기존 unittest, Solar/선택형 NVIDIA 전송 어댑터.

**Spec:** `specs/ai-developer/04-analysis-provider/grouped-semantic-review/spec.md`

## Global Constraints

- 기본 분석기·FastAPI·공개 Profile은 불변이다. 선택형 평가에서만 `grouped_review=True`를 사용한다.
- 고정 묶음 A 5필드, B 4필드, C `features` 1필드이며 세 묶음의 검토 성공 전 자동 완료 금지.
- 최초 추출 2회, 구조 수정 최대 1회, 묶음 검토 3회로 최대 6호출. 묶음 이슈 후 의미 수정·재검토 없음.
- 평가 결과에는 원문·원본 응답·키·Profile을 저장하지 않는다. 공개 PRD는 튜닝 자료다.

## Review Focus

- 마지막 묶음 응답이 실패하면 앞의 두 묶음이 정상이더라도 자동 완료하지 않는다: Task 2 테스트.
- 검토 응답이 묶음 밖 필드를 이슈로 반환하면 보류한다: Task 1 테스트.
- 같은 배열 ID의 중복/잘못된 ID와 missing의 빈 근거 줄은 보류한다: Task 1 테스트.
- 구조 수정이 1호출을 사용해도 묶음 3호출은 정확히 6회 안에서 끝나고 추가 호출하지 않는다: Task 2 테스트.
- `issues=[]`가 세 묶음에서 나와도 확인하지 않은 필드가 있으면 자동 완료하지 않는다: Task 2 테스트.

---

### Task 1: 묶음 응답 계약

**Files:** Create `ai_service/agentfit_ai/grouped_review.py`; Test `ai_service/tests/test_grouped_review.py`.

**Interfaces:** `GROUPS: tuple[tuple[str,...], ...]`; `group_review_payload(document, profile, fields, *, model, effort) -> dict`; `normalize_group_review(reply, profile, document, fields) -> dict` returns `{"checkedFields": list(fields), "issues": list[validated issue]}` or raises `ReviewValidationError`.

- [x] **Step 1: 실패 테스트 작성.** 세 묶음의 합집합·중복 없음, schema의 묶음 필드 제한, 정상 기존 항목/누락 오류 변환, `checkedFields` 누락·중복·묶음 밖 이슈·잘못된 ID·빈 missing 근거 거부를 검증한다.
- [x] **Step 2: 실패 확인.** `rtk proxy ../.venv/Scripts/python.exe -m unittest tests.test_grouped_review -q` → 실패.
- [x] **Step 3: 구현.** 기존 `compact_review.item_ids`·`normalize_compact_review`의 검증과 서버 근거 계산을 재사용한다. 그룹별 초안과 출력 schema만 새 모듈이 책임진다.
- [x] **Step 4: 테스트 통과 확인.** 위 명령 → 통과.
- [x] **Step 5: Task 1 코드·테스트 커밋.**

### Task 2: 분석 루프 연결과 안전 보류

**Files:** Modify `ai_service/agentfit_ai/solar.py`, `ai_service/agentfit_ai/source_selector_analysis.py`; Test `ai_service/tests/test_source_selector_analysis.py`, `ai_service/tests/test_nvidia_source_selector.py`.

**Interfaces:** `SolarAnalyzer._semantic_review_groups() -> tuple[tuple[str,...], ...]` default `(FIELDS,)`; `SolarAnalyzer._request_group_review(document, profile, fields, *, _trace=None, timeout=40)` opt-in hook; `SourceSelectorSolarAnalyzer(..., grouped_review=False)` implements the grouped hooks and invokes Task 1. Default `_request_review` remains unchanged.

- [x] **Step 1: 실패 테스트 작성.** 세 정상 응답 후 완료, 의미 이슈가 하나라도 있으면 확인 필요·의미 수정 없음, 구조 수정 뒤 총 6호출, 마지막 묶음 실패 보류, 기본 1회 검토, NVIDIA 전송 경로를 확인한다.
- [x] **Step 2: 실패 확인.** `rtk proxy ../.venv/Scripts/python.exe -m unittest tests.test_source_selector_analysis tests.test_nvidia_source_selector -q` → 새 테스트 실패.
- [x] **Step 3: 구현.** 기존 `_analyze`의 단일 검토 경로는 유지하고 opt-in 분기에서 세 호출·각 응답 검증·필드 합집합 확인 후 이슈를 한 번 관측한다. 이슈가 있으면 `SEMANTIC_REJECTED`로 복구 초안을 만들고 추가 호출하지 않는다. 한 호출 오류도 기존 `AnalysisError`로 안전 보류한다. 진단 stage는 기존 `semantic_review`를 쓰고 해당 묶음 필드를 기록한다.
- [x] **Step 4: 관련 테스트 통과 확인.** 위 명령 → 통과.
- [x] **Step 5: Task 2 코드·테스트 커밋.**

### Task 3: 평가 CLI와 실제 문서 판단

**Files:** Modify `ai_service/agentfit_ai/public_holdout_evaluation.py`; Test `ai_service/tests/test_public_holdout.py`; Create `specs/ai-developer/04-analysis-provider/grouped-semantic-review/validation.md`.

**Interfaces:** `--grouped-review` requires `--source-selector`, excludes `--compact-review`, records `grouped_review` and per-call 4096-token limit in plan. `--extended-review-window` may combine with grouped review; all other default options remain unchanged.

- [x] **Step 1: 실패 테스트 작성.** 허용·금지 CLI 조합, 실제 분석기 옵션, 기본 옵션 불변, plan 기록 및 원문 비저장을 확인한다.
- [x] **Step 2: 실패 확인.** `rtk proxy ../.venv/Scripts/python.exe -m unittest tests.test_public_holdout -q` → 새 테스트 실패.
- [x] **Step 3: CLI 연결.** grouped 리뷰는 opt-in에서만 전송한다. 안전 집계는 stage·고정 오류·숫자 진단만 남긴다.
- [x] **Step 4: 전체 테스트.** `rtk proxy ../.venv/Scripts/python.exe -m unittest discover -s tests -q`와 `rtk proxy git diff --check` → 성공.
- [x] **Step 5: Campfire PRD 1건.** 600초 평가에서 3개 검토 응답, 자동 완료/확인 필요, 부분 정답, 미평가 값, 호출 수를 기록한다. 정상 완료와 오확정 없음이 확인될 때만 튜닝 PRD 5건 확대. 독립 서비스 품질로 해석하지 않는다.
- [x] **Step 6: 검증 기록·push·Linux CI.** 결과와 산출물 해시를 `validation.md`에 기록한다. 코드·SDD만 커밋해 `feature/grouped-semantic-review`로 push하고 CI를 확인한다.
