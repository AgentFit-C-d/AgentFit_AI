# Tasks: AI Profile 후보 검증

**Input**: [Spec](spec.md) · [Plan](plan.md)
**Scope**: FastAPI 내부 순수 검증 모듈. 외부 API 호출·DB·공개 HTTP 제외.

## Phase 1: Setup

- [x] T001 `specs/ai-developer/01-profile-contract/spec.md`, `plan.md`, `tasks.md`에 요구사항·경계·검증 순서를 기록한다.

## Phase 2: US1 — 일관된 Profile 초안 후보

- [x] T002 [US1] `ai_service/tests/test_profile.py`에 시작 사례와 필드 누락·타입·미정/빈 배열 테스트를 작성하고 실패를 확인한다.
- [x] T003 [US1] `ai_service/agentfit_ai/profile.py`에 10개 필드·타입·문자열/배열 한도와 출처·미확정 계산을 구현한다.

## Phase 3: US2 — 문서 근거 검증

- [x] T004 [US2] `ai_service/tests/test_profile.py`에 근거 누락·범위·값 불일치·미정 근거·Unicode 사례를 작성하고 실패를 확인한다.
- [x] T005 [US2] `ai_service/agentfit_ai/profile.py`에 위치·값 대조와 원문 없는 안전 오류를 구현한다.

## Phase 4: 검증·인계

- [x] T006 `ai_service/tests/test_profile.py` 전체를 로컬 Python으로 실행하고 `specs/ai-developer/01-profile-contract/validation.md`에 결과·제외 범위를 기록한다.
- [x] T007 `specs/ai-developer/01-profile-contract/handoff-draft.md`에 확정된 순수 검증 결과와 FastAPI·Spring Boot 통합 시 필요한 변환을 반영한다.

**의존성:** T001 → T002 → T003 → T004 → T005 → T006 → T007. US1은 구조·출처를, US2는 근거를 독립적으로 확인할 수 있다. 이번 MVP는 US1+US2의 순수 모듈이며 HTTP 연동은 후속 기능이다.
