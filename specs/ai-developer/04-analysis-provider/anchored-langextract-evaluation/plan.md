# 문맥 인용 기반 LangExtract 근거 평가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 반복된 후보 문구에 고유한 원문 문맥 인용을 붙여 안전하게 위치를 검증하고 고정 18건을 재평가한다.

**Architecture:** LangExtract 추출 속성에 `anchor`를 추가하고, 독립 서버 검증 함수가 정확 문자열과 고유성을 검사한다. 평가기는 같은 문서의 두 골드를 한 모델 출력으로 채점하며 안전한 수치만 기록한다.

**Tech Stack:** Python 3.13, LangExtract 1.7.0(분리된 실험 venv), 기존 Solar 전송, unittest.

**Spec:** `specs/ai-developer/04-analysis-provider/anchored-langextract-evaluation/spec.md`

## Global Constraints

- 공개 Profile, FastAPI 기본 분석기, PDF worker, Spring 계약은 변경하지 않는다.
- 라이브 입력은 SHA-256 고정 합성 18건만 허용하고 `--live`가 필요하다.
- 원문·후보·anchor·키·원본 응답은 안전 결과와 일반 로그에 쓰지 않는다.
- 반복 후보의 출력 순서/개수만으로 위치를 배정하지 않는다.

## Review Focus

- 동일 후보 두 번이 같은 anchor를 가리키면 두 번째를 확정하지 않는다. Task 1 테스트.
- anchor가 원문에서 두 번 등장하면 후보 위치를 고르지 않는다. Task 1 테스트.
- 라이브러리 정렬 위치와 anchor 위치가 다르면 자동 허용하지 않는다. Task 1 테스트.
- 원문 한 번 등장 후보라도 제출 anchor가 충돌하면 기존 fallback을 적용하지 않는다. Task 1 테스트.
- 한 원문 짝 사례 중 호출이 실패하면 두 사례 모두 실패로 계수한다. Task 3 테스트.

---

### Task 1: 독립 문맥 위치 검증

**Files:** Create `ai_service/agentfit_ai/anchored_grounding.py`; create `ai_service/tests/test_anchored_grounding.py`.

**Interfaces:** `ground_anchored_extractions(document: str, extractions: list) -> tuple[dict, ...]`. 각 행은 `status`, `start`, `end`, `reason`의 안전한 값만 가진다. 원문·인용은 반환하지 않는다.

- [x] 실패 테스트: 다른 문맥의 같은 이름은 서로 다른 위치에 결속하고, 중복 anchor/원문 중복 anchor/문맥 내 후보 중복/정렬 충돌/누락·변형 문맥은 `review`로 처리한다.
- [x] `rtk proxy ../.venv/Scripts/python.exe -m unittest discover -s tests -p test_anchored_grounding.py -q`로 기대한 실패를 확인한다.
- [x] 원문 정확 문자열 검색과 중복 최종 위치 검증을 구현한다.
- [x] 같은 테스트로 통과를 확인하고 구현·테스트를 커밋한다.

### Task 2: LangExtract 속성·Solar 스키마 연결

**Files:** Modify `ai_service/agentfit_ai/langextract_solar_trial.py`, `ai_service/tests/test_langextract_solar_trial.py`.

**Interfaces:** `candidate_payload(prompt: str) -> dict`는 `candidate_attributes.anchor`를 필수로 요구한다. `score_case`는 Task 1의 검증 행을 사용한다.

- [x] 실패 테스트: 정확 JSON 스키마, 두 반복 위치의 서로 다른 anchor, 하나의 anchor를 중복 출력한 경우의 보류, anchor가 없는 반복 후보의 보류를 검증한다.
- [x] 대상 테스트를 실행해 기대한 실패를 확인한다.
- [x] 한국어 조사에 붙은 후보를 포함하는 원문 연속 구간을 복사하도록 모델 예시·프롬프트를 바꾸고 검증 함수를 연결한다.
- [x] 대상 및 전체 서비스 테스트를 통과시키고 커밋한다.

### Task 3: 짝 사례의 단일 추출과 안전한 실측

**Files:** Modify `ai_service/agentfit_ai/langextract_solar_trial.py`, `ai_service/tests/test_langextract_solar_trial.py`; create `specs/ai-developer/04-analysis-provider/anchored-langextract-evaluation/validation.md`.

**Interfaces:** 기존 `--all` 및 `--case-id` CLI를 유지한다. `--all`은 같은 `document`를 가진 사례에서 한 번 추출한 후보를 재사용한다.

- [x] 실패 테스트: 같은 문서의 두 골드는 한 번만 추출하고, 실패는 두 행 모두에 남기며, 저장 결과에 원문·anchor가 없는지 확인한다.
- [x] 대상 테스트를 실행해 기대한 실패를 확인한다.
- [x] 평가 루프에서 문서별 결과를 재사용하고 호출 수를 안전 집계한다.
- [x] 전체 테스트와 `git diff --check`를 통과시킨다.
- [x] 합성 R01/R02 실측 후 18건으로 확대한다. 자동 오확정·실패·누락·정확 위치를 이전 안전 설정과 나란히 기록한다.
- [x] 독립 코드 리뷰와 Linux CI를 확인하고 `feature/anchored-langextract-evaluation`에 push한다. 발견된 중복 판정 결함 2건을 수정하고 합성 18건을 재평가했다. 기본 서비스로 병합하지 않는다.
