# Tasks: Vercel skills.sh 인증 시험

**Status**: 로컬 구현·검증 완료, Preview 실호출 대기

## Phase 1: Setup

- [X] T001 `experiments/vercel-skills-api-probe/package.json`과 `.gitignore`를 만들고 비밀 값·Vercel 로컬 설정 제외를 확인한다.

## Phase 2: User Story 1 — 실제 검색 인증

**Independent test**: 유효한 입력에 대해 요청 시점 토큰으로 검색 API 한 번을 호출하고 제한된 후보 정보를 반환한다.

- [X] T002 [US1] `experiments/vercel-skills-api-probe/test/search.test.js`에 토큰 사용·검색 성공·빈 결과의 실패 테스트를 작성해 Red를 확인한다.
- [X] T003 [US1] `experiments/vercel-skills-api-probe/api/search.js`에 최소 검색 함수를 구현해 Green을 확인한다.

## Phase 3: User Story 2 — 시험 경계 보호

**Independent test**: 권한 없는 호출과 잘못된 입력은 외부 호출 전에 거부되고 오류가 안전하게 정규화된다.

- [X] T004 [US2] `experiments/vercel-skills-api-probe/test/search.test.js`에 접근 거부·입력 한도·401·429·5xx·비정상 응답의 실패 테스트를 작성해 Red를 확인한다.
- [X] T005 [US2] `experiments/vercel-skills-api-probe/api/search.js`에 접근 검사·입력 제한·오류 매핑을 구현해 Green을 확인한다.

## Phase 4: Validation

- [X] T006 `experiments/vercel-skills-api-probe/README.md`에 프로젝트 연결·OIDC 활성화·비밀 설정·Preview 호출·정리 절차를 적는다.
- [X] T007 `experiments/vercel-skills-api-probe/`의 테스트와 정적 검사를 수행하고 `specs/003-vercel-skills-api-probe/validation.md`에 기록한다.
- [ ] T008 Vercel Preview에서 실제 skills.sh 호출을 수행할 수 있으면 응답 상태·시각·후보 수만 `specs/003-vercel-skills-api-probe/validation.md`에 기록한다. 실행 불가면 미검증으로 기록한다.

## Dependencies

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008. 한 프로브 함수와 시험 파일을 순서대로 다루므로 병렬 변경하지 않는다.
