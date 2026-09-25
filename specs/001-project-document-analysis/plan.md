# Implementation Plan: Project Document Analysis

> **아키텍처 재계획 필요 · 2026-09-25:** 팀의 확정안은 Next.js → Spring Boot → FastAPI이며 PostgreSQL은 Spring Boot만 접근한다. 아래 단일 Next.js 서버·Prisma·Node PDF Worker·OpenAI SDK 구조와 파일 경로는 이 결정과 충돌하므로 **구현 기준으로 사용하지 않는다**. 실패 건의 LLM 원본 응답은 실제 수신 시 최대 7일 오류 추적용으로 보관하기로 결정했다. 아래 `AI 원본 응답 미보관` 문구도 이전 기준이다. 내부 서비스 계약을 확인한 뒤 Plan·Research·Data Model·HTTP 계약·Tasks를 함께 개정한다. AI 범위 초안은 [FastAPI 서비스 경계·계약](../ai-developer/fastapi-service-contract.md)에 있다. 제품 요구사항·인수 기준은 별도 변경 전까지 유지한다.

**Branch**: 미생성 (Git 초기화 전) | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

**API 계약 보완**: 2026-09-08. DTO·공개 인증 경계·버전/출처 계산을 구체화했으며 새 Feature나 구현을 시작하지 않았다.

**2026-09-25 Provider·Client 변경 확인**: 초기 설정 대상 Client는 Codex다. 문서 분석은 [Solar Pro 4를 1차 평가](../ai-developer/provider-evaluation.md)한다. 아래 OpenAI Responses·SDK·모델·키·구현 파일 서술은 이전 구현 기준안이며 Solar 평가와 팀 계약 정합화 전에는 확정 구현 지시로 사용하지 않는다. 공통 Profile·보안·보관·성공 기준은 유지한다. Solar 채택 여부와 실제 적용 범위는 미검증이다.

**Input**: `specs/001-project-document-analysis/spec.md`

## Summary

GitHub 로그인 후 개인 프로젝트에 PDF·Markdown·직접 텍스트를 입력하고, AI 분석 초안을
확인·수정해 저장하는 첫 Vertical Slice를 구현한다. Next.js의 UI와 서버 기능을 한 프로젝트로
구성하고 PostgreSQL에 프로필·상태·최소 추적 정보만 저장한다. 원문은 요청 메모리에서만 처리한다.
Foundation의 프로젝트 생성·목록·상세와 사용자 선택에 따른 삭제 기능을 함께 포함한다.

## Technical Context

**Language/Version**: TypeScript 5.x, Node.js 24 LTS 운영 권장. 현재 로컬 Node 22.16.0은 선택 패키지의 engine 범위를 충족하며 로컬 검증에 사용 가능.

**Primary Dependencies**: Next.js 16.3.4, React/React DOM 19.2.8, Better Auth 1.7.3,
Prisma CLI/client/adapter-pg 7.10.0, pg 8.x, Zod 4.5.4, OpenAI SDK 7.10.0, pdfjs-dist 6.3.289.
설치 시 버전을 명시하고 package-lock.json으로 고정한다. Prisma의 latest가 8.0.0-rc.13을 가리켜도 사용하지 않는다.

**Storage**: PostgreSQL 17. Prisma migration과 JSON 프로필 컬럼 사용.
원문·추출문·AI 원본 응답·근거 인용문·provider token은 영구 저장하지 않는다.

**Testing**: Better Auth 1.7.3의 peer 범위에 맞는 Vitest 4.x, 실제 PostgreSQL integration tests, Playwright 1.63.0.
정확한 Vitest patch와 전체 engine·peer 조합은 T001에서 확인해 고정한다. 기존 Vitest 5.0.0 조합은 설치 충돌이 확인되어 사용하지 않는다. 설치·테스트 통과를 의미하지 않는다.
개발용 pdf-lib로 실제 합성 PDF fixture 생성. Mock 연동과 실제 GitHub/OpenAI 결과를 별도 기록.

**Target Platform**: Node runtime의 웹 애플리케이션. 개발 Windows, 배포는 원문 보관 통제를 검증한 Node 호스트.
Chromium 중심 UI 검증. Edge runtime·정적 호스팅, 서비스 공개 배포와 배포 자동화 구현은 범위 밖이다.
다만 배포 예정 Node 호스트에서 원문 보관 통제를 확인하는 T045는 첫 Feature의 필수 검증에 포함한다. 대상 환경이 미정이면 로컬 구현과 독립 검증을 진행하되 Feature 전체 완료는 보류한다.

**Project Type**: Next.js App Router 기반 Modular Monolith. npm 사용.

**Performance Goals**: Spec SC-008의 p95 60초. 요청 전체 deadline 60초 내에서 PDF worker 15초,
AI 40초, 나머지 저장·응답 예산을 배분한다. SDK 자동 재시도는 끄며 사용자가 재시도한다.
SC-008은 제출 동작부터 결과/명시적 실패 표시까지 브라우저에서 측정한다. 서버 Attempt 시각만으로 네트워크·표시 지연을 제외하지 않는다.

**Constraints**: 파일 10,485,760 bytes, PDF 100쪽, 텍스트 100,000 code points.
raw body를 스트리밍으로 제한한 후 파싱한다. 하나의 서버 인스턴스에서 동시 분석 최대 2건,
사용자별 진행 중 1건으로 제한하며 초과 요청은 재시도 가능한 오류를 반환한다.
PDF 파서는 별도 worker와 heap 제한을 사용하되 이를 전체 메모리·OS 보안 보장으로 표현하지 않는다.

**Scale/Scope**: 5인 팀·한 학기. 로그인, 프로젝트 목록, 프로젝트 작업 화면.
다른 AI Client 지원·추천·Config 생성은 구현하지 않는다. 외부 Credential은 서버 환경에서만 주입한다.

## Constitution Check

*GATE: 연구 시작 전 Spec과 설계 방향 검토 통과. 설계 완료 후 아래 대응을 재검토한다.
이 표의 통과는 설계 적합성이며 실제 동작·배포 검증 완료가 아니다.*

| 원칙 | 설계 대응 | 설계 판정 |
| --- | --- | --- |
| I Beginner First | 한국어 입력 안내, 출처·미확정 표시, 편집·오류 복구 | 통과 |
| II Explicit Permission | 세션·소유권·동일 출처 검사, 삭제 확인, 실행 도구 없음 | 통과 |
| III LLM Verification | Zod 구조 검증, 원문 근거 대조, 미정 유지, 사용자 확인 | 통과 |
| IV Verified Catalog | 이번 Feature에 Tool 추천 없음 | 범위 확인 |
| V Secret Isolation | server-only Credential, 입력·출력 검사, 토큰 미보관, 안전 오류 | 통과 |
| VI Preview | 프로젝트 삭제 대상과 연관 데이터 안내·확인. Config 변경 없음 | 통과 |
| VII Auditability | 원문 없는 프로젝트별 사건, 트랜잭션 기록, 프로젝트 삭제 시 제거 | 통과 |
| VIII Minimal MVP | 단일 앱·DB, 한 Provider adapter, 임시 worker만 사용 | 통과 |
| IX Testable | FR/SC → 계약·테스트·Tasks 추적, 실제/Mock 결과 구분 | 통과 |
| X Generation != Verification | 프로필 상태만 표시, 환경 검증 성공 표시 없음 | 통과 |

### Architecture and Boundaries

- `src/lib/auth.ts`: Better Auth + Prisma adapter, GitHub만 활성화.
  `user:email`만 요청하고 추가 scope·계정 연결·token 조회/갱신 경로는 서버에서 차단.
  OAuth token은 로그인에 사용 후 Account 저장 전 제거한다. Session은 DB에 두고 cookie cache는 끈다.
  공개 인증 HTTP는 sign-in/social·callback/github·get-session·sign-out의 지정 method만 허용한다.
  customSession과 대응 Client 타입으로 user.id/name·session.expiresAt만 공개한다. 서버 내부 세션 검증과 HTTP allowlist를 분리하고 Token·Account·불필요 개인 필드를 직렬화하지 않는다.
  SDK 프로토콜은 보존하되 안전한 인증 code/message와 고정 callback 목적지를 사용한다. 실제 쿠키·응답 적합성은 T007·T041·T042에서 확인한다.
- `src/lib/http.ts`: 보호 API의 세션, 동일 출처, body 크기, 오류 DTO, no-store 응답.
  상태 변경은 동일 origin만 허용하고 타인/없는 프로젝트는 같은 404로 처리한다.
  [API 상세/OpenAPI](../../Docs/api/README.md)의 DTO·상태/오류 조합·JSON 64 KiB·추가 필드 거부·X-Request-Id·Retry-After를 적용한다.
- `src/modules/projects/`: 소유권이 포함된 DB 질의, 생성·목록·상세·삭제.
  삭제는 FK cascade로 관계 데이터를 제거하며 늦은 분석 결과의 재생성을 금지한다.
- `src/modules/documents/`: raw PDF/Markdown/plain text를 메모리로 읽는다.
  PDF는 `scripts/pdf-worker.mjs`에서 순차 추출하며 timeout·disconnect 시 종료한다.
  원문을 DB·파일·queue에 넣지 않고 worker에 Credential 환경변수를 전달하지 않는다.
  body 읽기 전에 사용자/프로젝트/서버 동시 슬롯을 원자적으로 확보하고 모든 종료에서 해제한다.
- `src/modules/analysis/`: Provider interface → OpenAI Responses strict structured output.
  `store:false`, 도구·Files·background·conversation 없이 추출 텍스트만 전달한다.
  추출값의 인용 근거를 원문과 대조한 뒤 인용문은 버리고 위치만 저장한다.
- `src/modules/profiles/`: 공통 Zod 타입, unknownFields 재계산, 사용자 확인 저장.
  Project의 version과 분석 generation을 조건으로 한 갱신으로 오래된 수정·분석 결과를 차단한다.
  전체 10개 data 필드와 draftId/draftVersion 쌍을 검사하고 기준 초안/확인값과 비교해 출처·근거를 계산한다. null은 UNKNOWN, 같은 알려진 값은 출처 유지, 변경값은 USER이며 원문 근거를 제거한다.
  DRAFT/CONFIRMED version은 각각 증가시키며 확인 저장이 DRAFT를 자동 삭제하지 않는다.
- `src/modules/audit/`: 사건명·대상·시점·상태만 허용하는 DTO. 외부 오류 객체나 원문을 기록하지 않는다.
- 외부 호출 동안 DB 트랜잭션을 열어 두지 않는다. 시작·종료/실패·사용자 저장을 각각 짧은 트랜잭션으로 처리한다.
  만료된 진행 중 Attempt는 다음 조회·요청에서 실패로 정리하며 원문을 복구하거나 재실행하지 않는다.

### Document and Failure Policy

UTF-8 Markdown은 텍스트로만 처리하며 HTML·MDX 렌더링과 링크 다운로드를 하지 않는다.
PDF는 알려진 파싱 오류·잠금·전체 빈 텍스트를 거부한다. 텍스트가 있는 페이지와 없는 페이지가
섞이면 부분 추출 의심으로 거부한다. 빈 페이지도 거부될 수 있음을 안내한다.
모든 PDF 입력에 이미지 내용은 분석되지 않는다고 표시한다. OCR 없이 의미적 완전성을 보장하지 않는다.

Secret 검사는 명확한 key/token 형식, credential assignment, private-key block 등을 대상으로
입력·파일명·프로필에 적용한다. 식별되면 요청/저장을 차단하고 유형만 안내한다.
임의의 모든 문자열이 Secret인지 판별할 수 있다고 주장하지 않는다.

초안과 확인 프로필은 분리한다. AI가 실패해도 기존 확인 프로필을 읽고 수정할 수 있다.
직접 작성 저장은 source=user로 표시한다. UI는 입력·수정값과 저장 성공을 혼동하지 않는다.

### Semantic and Outcome Evaluation

- FR-010–012: 원문 근거 존재 검사는 의미 정확성을 대체하지 않는다. 부정·후보/확정·현재/미래·다른 대상·상충·문맥 제한을 구분하고 명시적인 확정값을 추출한다.
- SC-011: 6범주별 2개 이상, 총 12개 합성 의미 사례. PDF·Markdown·직접 텍스트를 모두 포함하고 각 범주의 확정값 대조 사례와 미정/다른 값 사례를 사전 정의한다.
- SC-012: 정상 외부 서비스·지원 입력 정책에서 독립 정상 문서 30개, 유형별 10개를 평가한다. 유형별 짧음 4개·중간 4개·한도에 가까움 2개를 준비하고 길이·PDF 페이지·필수 기대 사실을 사전에 기록한다. 거부가 정답인 문서는 ERROR 묶음으로 분리한다.
- SC-003 사실 정답 9개는 NORMAL에서 유형별 3개를 선택해 재사용할 수 있다. SEM은 NORMAL과 겹치더라도 의미 판정을 별도로 집계한다.
- 첫 요청에서 검증된 초안이 저장·표시되고 사전 필수 사실을 충족하면 성공이다. 30개 중 29개 이상 성공해야 95% 기준을 충족한다. 시간 초과·Provider/저장 오류·재시도 성공은 첫 요청 성공으로 세지 않는다.
- 전체 60초 내 결과/실패 안내, 성공 분석 지연, 실패 안내 지연과 정상 성공률을 따로 보고한다. 측정은 단일 실행 중 유리한 요청만 골라 재집계하지 않는다.
- `scripts/evaluate-analysis.ts`와 `tests/fixtures/expected.json`에 FACT/SEM/NORMAL/ERROR 묶음, 실행 조건·정답·결과·분모를 기록한다. fixture는 합성 데이터이며 사용자 원문·전체 Provider 응답·Secret은 저장하지 않는다.
- 근거 UI는 위치·출처와 원문 미보관을 설명한다. 서버 원문 재열람·인용 저장을 추가하지 않는다.
- `Docs/validation-plan.md`의 제품 비교·설정 검증은 후속 흐름의 별도 평가이며 첫 Feature의 작업 완료나 실제 결과로 집계하지 않는다.

### Operational and External Gates

- 실제 GitHub OAuth App, 서버 Credential, OpenAI Key, 실행 중 PostgreSQL이 필요하다.
  현재 Credential 설정 여부는 확인하지 않았으며 Docker engine은 첫 조회에서 미실행이었다.
- 원문 미보관은 AgentFit의 관리 저장소 기준이다. 운영 전에 body logging/spooling,
  request tracing, swap, core/heap dump, 외부 업로드 저장을 통제하고 crash 시 잔존 검증을 해야 한다.
  JavaScript 문자열의 즉시 물리적 RAM 소거를 보장하지 않는다.
- `store:false`는 OpenAI의 모든 보관을 제거하지 않는다. 외부 정책을 입력 화면에 설명한다.
- 사실 정답 최소 9개·의미 사례 12개·정상 입력 30개의 실제 평가, 5명 사용성 평가, 실제 OAuth 검증과 지연·성공률 측정 전 Feature 완료를 선언하지 않는다.

## Project Structure

### Documentation (this feature)

```text
specs/001-project-document-analysis/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/http.md
├── checklists/requirements.md
├── checklists/security-ux.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── page.tsx
│   ├── projects/page.tsx
│   ├── projects/[projectId]/page.tsx
│   └── api/
│       ├── auth/[...all]/route.ts
│       └── projects/
│           ├── route.ts
│           └── [projectId]/
│               ├── route.ts
│               ├── analysis/route.ts
│               └── profile/route.ts
├── components/
│   ├── login-button.tsx
│   ├── project-list.tsx
│   └── project-workspace.tsx
├── lib/
│   ├── auth.ts
│   ├── auth-client.ts
│   ├── db.ts
│   ├── env.ts
│   └── http.ts
├── modules/
│   ├── projects/service.ts
│   ├── documents/{input,extract,pdf}.ts
│   ├── analysis/{provider,openai,service,evidence}.ts
│   ├── profiles/{schema,service}.ts
│   ├── security/secrets.ts
│   └── audit/events.ts
└── generated/prisma/
prisma/schema.prisma
prisma/migrations/
scripts/{pdf-worker.mjs,generate-fixtures.mjs,evaluate-analysis.ts}
tests/{unit,integration,e2e,fixtures}/
package.json
package-lock.json
prisma.config.ts
next.config.ts
tsconfig.json
eslint.config.mjs
vitest.config.ts
playwright.config.ts
compose.yaml
.env.example
README.md
```

**Structure Decision**: UI와 API가 같은 검증 타입과 모듈을 사용하는 단일 Next 앱.
Prisma만 schema/migration을 소유한다. Source tree는 구현 예정 경로이며 현재 존재한다고 표시하지 않는다.

## Complexity Tracking

헌법 위반 없음. PDF worker는 시간 제한을 실제 적용하기 위한 동일 앱의 보조 실행 단위이며
독립 Microservice·Queue·Agent Framework를 도입하지 않는다.
