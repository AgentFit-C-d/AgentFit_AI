# Tasks: Project Document Analysis

> **실행 보류 · 2026-09-25:** 아래 T001–T047의 구현 경로·프레임워크·의존성 순서는 단일 Next.js 서버 계획에 묶여 있다. 팀 확정안인 Next.js → Spring Boot → FastAPI와 PostgreSQL의 Spring Boot 단독 접근을 반영해 재생성하기 전에는 구현 체크리스트로 사용하지 않는다. 실패 건의 LLM 원본 응답은 실제 수신 시 최대 7일 오류 추적용으로 보관한다. 제품 요구사항과 평가 목표는 유지하되, 서비스 간 계약을 합의한 후 담당·선행 관계를 다시 배정한다. [AI 서비스 경계 초안](../ai-developer/fastapi-service-contract.md)을 참고한다.

**Input**: `specs/001-project-document-analysis/`의 Spec·Plan·Research·Data Model·Contracts.
**Prerequisites**: Constitution 1.0.0, 사용자 Clarification 5개, 구현 전 Analyze 통과.
**Tests**: 인수인계와 Spec에서 요청했다. 테스트를 먼저 작성해 실패를 확인한 후 해당 기능을 구현한다.
**Organization**: Setup → Foundation → US1 → US2 → US3 → US4 → 전체 검증.

**2026-09-25 변경 확인**: 초기 설정 대상 Client는 Codex이며, Solar Pro 4가 문서 분석의 1차 평가 모델이다. T018·T021의 OpenAI Responses 세부 구현은 기존 기준안이다. T021 착수 전에 [Provider 평가](../ai-developer/provider-evaluation.md)와 팀의 Profile·Provider 오류 계약을 확인하고 Plan·Task의 모델·SDK·파일 경로를 정합화한다. 현재 체크된 완료 작업은 없다.

## Format: `[ID] [P?] [Story] Description`

`[P]`는 같은 단계에서 선행 작업이 끝난 뒤 다른 파일과 독립적으로 진행 가능한 작업이다.
체크는 실제 완료 증거가 있을 때만 갱신한다. 상대 경로는 저장소 루트 기준이다.

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Node·npm 및 전체 engine·peer 호환성을 확인하고 버전을 고정한다. Better Auth와 충돌하는 Vitest 5는 제외하고 호환되는 4.x patch를 선택한다. Next/React/TypeScript·서버·테스트 의존성과 실행 명령을 `package.json`, `package-lock.json`, `tsconfig.json`, `next.config.ts`에 구성한다.
- [ ] T002 [P] 린트·Vitest·Playwright 설정을 `eslint.config.mjs`, `vitest.config.ts`, `playwright.config.ts`에 구성한다.
- [ ] T003 [P] Git 저장소와 Feature Branch를 준비하고 Secret·캐시·생성물 제외를 `.gitignore`, 서버 설정 예시를 `.env.example`, 로컬 DB를 `compose.yaml`에 정의한다.

## Phase 2: Foundational (Blocking Prerequisites)

**Checkpoint**: 공통 타입·인증·DB·오류 경계가 준비된 뒤 사용자 흐름을 구현한다.

- [ ] T004 Auth 및 프로젝트 Entity·FK·unique/version·cascade를 `prisma/schema.prisma`, `prisma/migrations/`, `prisma.config.ts`에 정의하고 `src/lib/db.ts`에 단일 Prisma client를 구성한다. (FR-001, FR-015, FR-020–021, FR-024)
- [ ] T005 [P] Profile 값·출처·미확정·근거 위치 schema와 입력 검증을 `src/modules/profiles/schema.ts`에 정의한다. (FR-009–012, FR-014) API의 10개 필드·nullable·빈 배열·공개 DTO 제약을 동일 schema에 맞춘다.
- [ ] T006 [P] Secret 검사와 안전 오류·환경 경계를 `src/modules/security/secrets.ts`, `src/modules/audit/events.ts`, `src/lib/env.ts`에 구현한다. (FR-018–020)
- [ ] T007 GitHub-only Better Auth, scope 입력 차단·불필요 endpoint 차단·token null 훅·DB 세션을 `src/lib/auth.ts`, `src/lib/auth-client.ts`, `src/app/api/auth/[...all]/route.ts`에 구성한다. (FR-003, FR-019) 공개 method/path allowlist·고정 callback·customSession의 토큰 없는 PublicSession·대응 Client 타입을 적용한다.
- [ ] T008 세션·Origin·크기·안전 응답·no-store·소유권 오류 규약을 `src/lib/http.ts`에 구현한다. (FR-003, FR-005, FR-017–019) OpenAPI의 HTTP/code 조합·64 KiB·X-Request-Id·Retry-After와 인증 SDK 오류 경계의 차이를 유지한다.
- [ ] T009 Foundation의 Secret 유입·auth scope/token 경계·공통 schema 검증을 `tests/unit/security.test.ts`, `tests/unit/auth.test.ts`, `tests/unit/profile-schema.test.ts`에서 실행한다. (FR-003, FR-010, FR-012, FR-019, SC-006) 공개 세션 필드 allowlist·토큰/IP/UA/이메일/이미지 비노출·추가 인증 경로 기본 거부를 확인한다.

## Phase 3: User Story 1 - 프로젝트 생성·조회·삭제 (Priority: P1)

**Goal**: 로그인한 사용자가 본인 프로젝트를 만들고 다시 찾으며 명시적으로 삭제한다.
**Independent Test**: AI 없이 두 사용자의 프로젝트 조회·저장·삭제·격리를 검증한다.

- [ ] T010 [P] [US1] 생성·비로그인·타인/없는 프로젝트·Origin·삭제 취소/실패 계약 테스트를 `tests/unit/projects.test.ts`에 작성하고 실패를 확인한다. (FR-001–003, FR-017, FR-024)
- [ ] T011 [P] [US1] 실제 PostgreSQL fixture·안전한 테스트 DB 검사와 사용자 격리·cascade 테스트를 `tests/integration/setup.ts`, `tests/integration/projects.test.ts`에 작성한다. (FR-003, FR-021, FR-024, SC-009–010)
- [ ] T012 [US1] 소유권을 포함한 생성·목록·상세·삭제와 안전한 트랜잭션을 `src/modules/projects/service.ts`에 구현한다. (FR-001–003, FR-017, FR-024)
- [ ] T013 [US1] 프로젝트 API를 `src/app/api/projects/route.ts`, `src/app/api/projects/[projectId]/route.ts`에 연결한다. (FR-001–003, FR-024)
- [ ] T014 [US1] 한국어 앱 shell·로그인·목록·빈 상태·삭제 확인을 `src/app/layout.tsx`, `src/app/globals.css`, `src/app/page.tsx`, `src/app/projects/page.tsx`, `src/components/login-button.tsx`, `src/components/project-list.tsx`에 구현한다. (FR-001–003, FR-023–024) 제한된 공개 세션 타입과 SDK 로그인/로그아웃을 사용하고 세션 없음과 인증 저장소 장애를 구분한다.
- [ ] T015 [US1] US1 테스트를 실행하고 결과를 `specs/001-project-document-analysis/validation.md`에 기록한다. 실제 GitHub 검증은 T042로 구분한다. (SC-001, SC-009–010)

## Phase 4: User Story 2 - 문서 입력·분석 초안 (Priority: P1)

**Goal**: 실제 PDF·Markdown·직접 텍스트에서 검증된 분석 초안을 만든다.
**Independent Test**: 준비된 프로젝트에서 입력 경계·실제 파서·대체 Provider 계약으로 분석 흐름을 검증한다.

- [ ] T016 [P] [US2] 합성 PDF·Markdown·텍스트 fixture와 사전 정답표를 `scripts/generate-fixtures.mjs`, `tests/fixtures/`에 준비한다. FACT 9개(유형별 3), SEM 12개(6범주×2, 확정 대조 포함), NORMAL 30개(유형별 10)의 목적·재사용·분포·필수 사실을 Plan 기준으로 고정하고 ERROR를 분리한다. (FR-004–007, FR-010–012, SC-001–003, SC-011–012)
- [ ] T047 [US2] T016의 사전 정답 기준을 바꾸지 않고 Solar Pro 4 공식 API의 구조화 출력·거절/불완전 응답·인증·데이터 처리 조건을 확인하고, 승인된 합성 입력으로 제한된 실제 호출 평가를 수행한다. 모델·설정·표본·비용·품질·지연을 기록하고 Provider 구현 전 Plan·T018·T021·Quickstart를 팀 계약에 맞게 갱신한다. 이 시험을 T043의 전체 저장·표시 성공률 검증으로 대체하지 않는다.
- [ ] T017 [P] [US2] 10 MiB·100쪽·100,000 code-point 경계 및 잘못된 입력 테스트를 `tests/unit/documents.test.ts`에 작성하고 실패를 확인한다. (FR-004–007)
- [ ] T018 [P] [US2] 구조 오류·근거 없음·거절·store:false·Secret 유입 방지 Provider 테스트를 `tests/unit/analysis-provider.test.ts`에 작성하고 실패를 확인한다. (FR-009–012, FR-018–019, SC-002, SC-006) 부정·후보·다른 대상의 근거 문자열과 실제 의미를 구분하는 실패·확정 대조 사례를 포함한다. (SC-011)
- [ ] T019 [US2] 인증 후 raw body의 제한·유형·파일명 검증과 텍스트 추출을 `src/modules/documents/input.ts`, `src/modules/documents/extract.ts`에 구현한다. (FR-004–007, FR-019)
- [ ] T020 [US2] 종료 가능한 PDF worker와 페이지·문자·부분 추출 검증을 `scripts/pdf-worker.mjs`, `src/modules/documents/pdf.ts`에 구현한다. (FR-005–007, FR-021)
- [ ] T021 [US2] Provider interface·OpenAI strict output·근거 대조·safe error를 `src/modules/analysis/provider.ts`, `src/modules/analysis/openai.ts`, `src/modules/analysis/evidence.ts`에 구현한다. (FR-008–012, FR-018–019) 문자열 존재를 확정 근거로 단정하지 않는 Prompt·의미 검토·불확실성 처리를 적용하고 합성 정답으로 확인한다. (FR-010–012, SC-011)
- [ ] T022 [US2] 분석 시작·현재 generation·deadline·동시 제한·초안 저장·Audit를 `src/modules/analysis/service.ts`에 구현한다. (FR-012–013, FR-015, FR-020–021) body 읽기·Worker 시작 전 슬롯 확보와 모든 종료 경로의 반환을 보장한다.
- [ ] T023 [US2] raw 입력 endpoint와 취소·timeout 처리를 `src/app/api/projects/[projectId]/analysis/route.ts`에 연결한다. (FR-004–008, FR-013, FR-016)
- [ ] T024 [US2] 파일/텍스트 입력·제한·고지·진행·초안 화면을 `src/app/projects/[projectId]/page.tsx`, `src/components/project-workspace.tsx`에 구현한다. (FR-004–008, FR-011, FR-013, FR-022–023)
- [ ] T025 [US2] 실제 파서·저장 초안·만료 Attempt 검증을 `tests/integration/analysis.test.ts`에서 실행하고 `specs/001-project-document-analysis/validation.md`에 실제/Mock 범위를 기록한다. (SC-001–003, SC-006, SC-010) 유효 초안 저장과 사전 필수 사실 충족을 성공으로 판정하는 조건을 확인한다. (SC-012)

## Phase 5: User Story 3 - 사용자 확인·수정·저장 (Priority: P1)

**Goal**: 사용자가 AI 결과를 수정하고 재접속 후에도 확인 프로필을 유지한다.
**Independent Test**: 준비된 초안을 수정하고 미정/없음·출처·충돌·저장 실패를 검증한다.

- [ ] T026 [P] [US3] 수정·미정/없음·출처 변경·저장 실패·오래된 version 테스트를 `tests/unit/profiles.test.ts`에 작성하고 실패를 확인한다. (FR-010–011, FR-014–017) draft 필드 쌍·초안/확인값 기준 선택·같은 값/변경/null/[]의 출처·근거 보존을 포함한다.
- [ ] T027 [US3] confirmation·expectedVersion·draftVersion 검증과 Audit 저장을 `src/modules/profiles/service.ts`에 구현한다. (FR-014–015, FR-017, FR-020) data 전체 10개 필드·기준 Profile 비교·출처/근거 재계산·각 Profile 버전 증가를 같은 저장 경계에서 처리한다.
- [ ] T028 [US3] 프로필 수정 API를 `src/app/api/projects/[projectId]/profile/route.ts`에 연결한다. (FR-003, FR-014–015, FR-017)
- [ ] T029 [US3] 필드 편집·미정/없음·근거/출처·저장 실패 보존·충돌 안내를 `src/components/project-workspace.tsx`에 통합한다. (FR-011, FR-014–017, FR-023) 근거 위치는 원문 재열람 기능이 아님을 안내하고 서버에 원문 인용을 보관하지 않는다. (FR-011)
- [ ] T030 [US3] 실제 DB 동시 저장·재분석 보존·재접속 검증을 `tests/integration/profiles.test.ts`에서 실행한다. (FR-015, SC-002, SC-004)

## Phase 6: User Story 4 - 실패 복구와 보관 제어 (Priority: P1)

**Goal**: 실패를 안전하게 설명하고 재시도/직접 작성으로 복구하며 원문을 보관하지 않는다.
**Independent Test**: 추출·AI·저장 실패와 분석 중단을 주입해 기존 프로필 및 잔존 데이터를 확인한다.

- [ ] T031 [P] [US4] 잠금·손상·부분 PDF·timeout·worker crash·AI 오류·저장 실패 시나리오를 `tests/unit/recovery.test.ts`에 작성하고 실패를 확인한다. (FR-006–007, FR-012, FR-016–017, FR-021)
- [ ] T032 [US4] 재입력 안내·수동 작성·오류 상태 보존을 `src/components/project-workspace.tsx`, `src/modules/analysis/service.ts`, `src/modules/profiles/service.ts`에 완성한다. (FR-013, FR-016–017)
- [ ] T033 [US4] 늦은 결과·프로젝트 삭제·중단 복구의 트랜잭션 조건과 Audit 안전성을 `src/modules/projects/service.ts`, `src/modules/analysis/service.ts`, `src/modules/audit/events.ts`에 보강한다. (FR-015, FR-020–021, FR-024)
- [ ] T034 [US4] raw/extracted canary의 DB·로그·임시 파일 잔존과 실패·삭제 race 검증을 `tests/integration/retention.test.ts`에 구현·실행한다. (FR-018–021, FR-024, SC-006, SC-010)
- [ ] T035 [US4] 정상·실패·미정·수동 작성의 사용자 흐름을 `tests/e2e/workflow.spec.ts`에서 검증한다. production 인증 우회를 추가하지 않는다. (SC-001–002, SC-004–006)

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T036 [P] 키보드·label·상태 안내·로그아웃 검증을 `tests/e2e/accessibility.spec.ts`에 추가한다. (FR-003, FR-023)
- [ ] T037 [P] FACT/SEM/NORMAL/ERROR를 분리하는 실제 평가 도구를 `scripts/evaluate-analysis.ts`, `tests/fixtures/expected.json`에 작성한다. 의미 정답·첫 요청 초안 저장/필수 사실 성공률·전체 응답 시간·성공/실패 지연·분모·환경을 기록하고 재시도와 오류를 정상 성공으로 집계하지 않는다. (SC-003, SC-008, SC-011–012)
- [ ] T038 설치·환경 설정·준비 상태·실제/Mock 검증·현재 범위를 `README.md`, `specs/001-project-document-analysis/quickstart.md`에 갱신한다.
- [ ] T039 build·typecheck·lint·unit을 실행하고 발견된 결함을 수정한 뒤 근거를 `specs/001-project-document-analysis/validation.md`에 기록한다.
- [ ] T040 독립 PostgreSQL의 integration 및 Playwright 검증을 실행해 `specs/001-project-document-analysis/validation.md`에 기록한다. DB 준비 실패는 통과로 기록하지 않는다. (SC-001–006, SC-009–010)
- [ ] T041 인증 scope 확장·token 조회·초기/재로그인 token NULL 검증을 `tests/integration/auth.test.ts`에서 실행하고 결과를 `specs/001-project-document-analysis/validation.md`에 기록한다. (FR-003, FR-019, SC-006) get-session의 토큰 없는 DTO·공개 인증 allowlist·SDK 프로토콜 적합성도 확인한다.
- [ ] T042 GitHub OAuth App·서버 Credential로 실제 로그인·취소·재로그인·두 사용자 격리를 검증하고 `specs/001-project-document-analysis/validation.md`에 기록한다. 외부 준비 조건이 충족되지 않으면 미완료로 둔다. (FR-003, SC-009)
- [ ] T043 승인된 합성 입력으로 실제 Provider·저장·표시를 연결해 FACT 정확도 90%, SEM 대상 필드 전부 정답, NORMAL 95% 첫 요청 성공(30개 중 최소 29개), 기존 95% 60초 안내 목표를 검증하고 성공/실패 지연·실패 표본을 분리 기록한다. (SC-003, SC-008, SC-011–012)
- [ ] T044 개발 초보자 5명의 사용성 평가를 진행해 `specs/001-project-document-analysis/validation.md`에 관찰 결과를 기록한다. 실행하지 않은 평가를 추정으로 채우지 않는다. (SC-007)
- [ ] T045 실제 운영 대상의 body spooling·로그·APM·swap·dump 설정과 crash 잔존을 점검하고 `specs/001-project-document-analysis/validation.md`에 기록한다. 운영 대상 미정이면 미완료로 둔다. (FR-021, SC-010)
- [ ] T046 Spec Kit converge로 누락된 필수 작업을 찾아 이 `specs/001-project-document-analysis/tasks.md`에 추가하고 남은 범위를 보고한다.

## Dependencies & Execution Order

- T001 → T002/T003 → Foundation(T004–T009) → US1 → US2 → US3 → US4 → 전체 검증.
- T005와 T006은 DB schema 작성과 독립적이다. T007은 T004, T008은 T006/T007 후 진행한다.
- 각 Story의 테스트를 먼저 작성해 의도한 실패를 확인하고 구현 후 다시 실행한다.
- US2 Provider 구현은 T016의 정답 고정 → T047의 Solar 계약·로컬 제한 평가 → Plan·T018·T021·Quickstart 정합화 순으로 진행한다. T047 실제 호출에는 사용자 측 Upstage API 접근이 필요하며 호출 수·비용은 기록한다.
- US2는 준비된 프로젝트, US3는 준비된 초안으로 독립 검증하지만 최종 화면 통합은 앞 Story에 의존한다.
- T025/T030/T034/T040/T041은 실제 PostgreSQL이 필요하다. 사용할 수 없으면 관련 검증을 미수행으로 남기고 독립적인 구현·unit 검증을 계속한다.
- T042/T043은 사용자 외부 Credential 설정, T044는 실제 참여자, T045는 운영 환경이 필요하다. T047의 API 호출도 사용자 측 Provider Credential이 있어야 한다.
- 사용자 Story 순서는 보존하되 외부 준비 조건을 기다리는 동안 독립적인 코드·문서·검증 도구 작업은 진행할 수 있다.

## Parallel Examples

- US1: T010 계약 테스트와 T011 독립 DB fixture 준비는 다른 파일에서 병행 가능.
- US2: T016 fixture와 T017 입력 테스트는 공통 계약을 읽고 병행 가능. T018의 Provider 세부 검증은 T047 이후 구현 Provider를 정합화하고 진행한다.
- US3: T026 테스트 작성과 이미 정의된 계약을 바탕으로 한 편집 화면 준비는 가능하나 T029 최종 통합은 T027/T028 이후.
- US4: T031 실패 fixture 작성은 UI 복구 준비와 병행 가능하나 최종 T034/T035는 서비스 완성 후.
- 이 예시는 작업 의존성 설명이며 별도 agent 위임 또는 외부 작업 실행을 뜻하지 않는다.

## Requirement Coverage

| Requirement | Task IDs |
| --- | --- |
| FR-001–002 | T010, T012–015 |
| FR-003 | T007–011, T013–015, T028, T036, T041–042 |
| FR-004–007 | T016–020, T023–025, T031 |
| FR-008 | T021, T023–024, T047 |
| FR-009–012 | T005, T009, T018, T021, T025–026, T047 |
| FR-013 | T022–024, T032 |
| FR-014–015 | T026–030, T033 |
| FR-016–017 | T023, T026–032 |
| FR-018–019 | T006–009, T018–021, T034, T041 |
| FR-020 | T004, T006, T022, T027, T033–034 |
| FR-021 | T004, T011, T020, T022, T031, T033–034, T045 |
| FR-022–023 | T014, T024, T029, T036 |
| FR-024 | T004, T010–015, T033–034 |
| SC-001–002 | T015–018, T025, T030, T035, T040 |
| SC-003 | T016, T025, T037, T043, T047 |
| SC-004–006 | T009, T018, T030, T034–035, T040–041 |
| SC-007 | T044 |
| SC-008 | T037, T043 |
| SC-009–010 | T011, T015, T025, T034, T040, T042, T045 |
| SC-011 | T016, T018, T021, T037, T043, T047 |
| SC-012 | T016, T025, T037, T043, T047 |

## Implementation Strategy

프로젝트 Foundation을 먼저 완성하고 문서 분석 → 확인 저장 → 실패 복구를 연결한다.
사용자에게 Mock·실제 동작·외부 준비가 필요한 검증을 구분해 보고한다.
첫 흐름의 필수 검증이 끝나기 전 추천이나 Config Feature로 진행하지 않는다.
