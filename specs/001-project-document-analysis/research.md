# Research: Project Document Analysis

**Date**: 2026-09-07
**Status**: 기술 선택 조사 완료. 설치·실행 검증 결과는 별도 기록한다.

## R1 — Modular Monolith와 버전 고정

- Decision: Next.js 16.3.4 / React 19.2.8 / TypeScript / npm, PostgreSQL 17, Prisma 7.10.0.
- Rationale: 팀 규모에 맞는 단일 앱에서 UI·인증·서버 검증을 공유한다. 현재 코드가 없어 교체할 기존 스택은 없다.
- Alternatives: 별도 Express 서버는 첫 흐름에 배포 단위를 추가한다. Prisma 8 RC는 채택하지 않는다.
- Evidence: 공식 npm registry의 version·engine을 조회했다. 로컬 Node 22.16.0은 선택 범위를 만족하며 운영은 Node 24 LTS를 권장한다.
- Sources: [Next 설치](https://nextjs.org/docs/app/getting-started/installation), [Node 릴리스](https://nodejs.org/en/about/previous-releases), [Prisma 7](https://www.prisma.io/docs/guides/upgrade-prisma-orm/v7).

## R2 — GitHub 로그인과 최소 권한

- Decision: Better Auth 1.7.3 + Prisma adapter + DB sessions. GitHub만 제공하고 user:email만 명시적으로 요청한다.
- Rationale: state·cookie·세션 처리를 유지보수되는 라이브러리에 맡기고 repository scope는 요청하지 않는다. GitHub numeric account id로 동일 계정을 연결한다.
- Restrictions: provider token은 Account 저장 전에 제거한다. 추가 scope·계정 연결·token 조회/갱신 경로는 서버에서 차단한다. 고정 trustedOrigins, DB session 검증, cookie cache 비활성화, 안전한 로그를 사용한다.
- Alternatives: Auth.js 공식 설치는 현재 beta 경로를 안내한다. 직접 OAuth 구현은 보안 검증 범위를 늘린다.
- Sources: [Better Auth GitHub](https://better-auth.com/docs/authentication/github), [Next 통합](https://better-auth.com/docs/integrations/next), [옵션](https://better-auth.com/docs/reference/options), [GitHub scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps), [Next 인증](https://nextjs.org/docs/app/guides/authentication).

## R3 — 문서 처리와 원문 미보관

- Decision: raw body 스트림의 바이트 제한, UTF-8 텍스트 해석, pdfjs-dist 6.3.289의 Node legacy entry를 자체 worker에서 실행한다.
- Rationale: 파일 저장과 multipart 의존성을 생략한다. PDF.js의 Node 내부 fake worker에 의존하지 않고 부모가 worker를 종료해 timeout을 적용한다.
- Limits: 10 MiB·100쪽·100,000 code points; PDF worker 15초, 동시 분석 2건. worker heap limit는 전체 메모리나 OS sandbox 보장이 아니다.
- PDF policy: 파싱·잠금·빈 텍스트 오류는 차단하고 일부 빈 페이지는 부분 추출 의심으로 거부한다. 이미지·다단 문서의 의미적 완전성은 보장하지 않는다.
- Alternatives: OCR·시각 분석은 첫 Feature 밖이다. 단순 Promise timeout은 CPU 파서를 중단시키지 못한다.
- Sources: [PDF.js 릴리스](https://github.com/mozilla/pdf.js/releases/tag/v6.3.289), [Node 예제](https://raw.githubusercontent.com/mozilla/pdf.js/v6.3.289/examples/node/getinfo.mjs), [Node Worker](https://nodejs.org/api/worker_threads.html), [Next 서버 패키지](https://nextjs.org/docs/app/api-reference/config/next-config-js/serverExternalPackages).

## R4 — 구조화된 AI 출력과 근거 검증

- Decision: OpenAI SDK 7.10.0 Responses + strict structured output, Zod 4.5.4. 기준 모델은 gpt-4.1-mini-2025-04-14이며 서버 설정으로 교체 가능하게 한다.
- Rationale: 지정 모델은 Responses·Structured Outputs를 지원한다. 최신·최상이라는 판단이 아니라 추출 작업의 초기 기준점이며 품질은 SC-003으로 평가한다.
- Policy: store:false, 자동 재시도 0, tools·Files·background·conversation 없음. 비밀이 아닌 고정 구조와 정제한 텍스트만 전달한다. 거절·불완전 응답·구조 오류는 실패 처리한다.
- Grounding: 값은 원문 표현을 추출하고 각 값의 근거 구절을 대조한다. 근거 없는 필드는 null로 둔다. 저장에는 필드값과 근거 위치만 남기고 인용문·전체 응답은 버린다. 의미적 정확도는 별도 정답 평가가 필요하다. 부정·후보·현재/미래·다른 대상·상충·문맥 제한은 SC-011로 검증한다. SC-012는 정상 첫 요청의 저장·표시·필수 사실 성공률을 별도로 평가해 빠른 오류가 성능을 대신하지 못하게 한다.
- Alternatives: 단순 JSON 모드는 구조 적합성을 보장하지 않는다. File 업로드·검색·Vector DB는 현재 흐름에 필요하지 않다.
- Sources: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-4.1 Mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

## R5 — 앱 삭제와 외부 보관 구분

- Decision: 원문은 AgentFit의 관리 저장소에 기록하지 않는다. 프로필·metadata·Audit는 프로젝트 삭제로 cascade 제거한다. OpenAI의 보관 조건은 별도로 고지한다.
- Evidence: store:false는 Responses의 저장을 제한하지만 기본 abuse monitoring 보관까지 없애는 설정은 아니다. 별도 승인 없이 Zero Data Retention을 보장하지 않는다.
- Operational gate: 배포 환경의 body spooling·로그·APM·swap·dump를 점검한다. 앱의 메모리 참조 해제를 물리적 RAM 즉시 소거라고 표현하지 않는다.
- Sources: [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data), [nginx request buffer](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_body_buffer_size), [Docker 메모리·swap](https://docs.docker.com/engine/containers/resource_constraints/).

## R6 — 상태·충돌·검증

- Decision: 분석 초안과 확인 프로필을 분리한다. version 조건 갱신과 FK cascade를 사용하고 네트워크 호출 밖에서 짧은 트랜잭션을 수행한다.
- Rationale: 오래된 결과의 덮어쓰기와 삭제 후 재생성을 막는다. 재시작 후 만료 Attempt는 원문 복원 없이 실패로 정리한다.
- Testing: 실제 합성 PDF, Vitest의 순수 검증·실패 시나리오, PostgreSQL 격리·cascade·동시성, Playwright 사용자 흐름, 별도의 실제 OAuth·AI 평가를 사용한다.
- Sources: [Prisma 동시성](https://www.prisma.io/docs/orm/v6/prisma-client/queries/transactions), [PDF fixture 생성](https://pdf-lib.js.org/).

## Remaining External Setup

기존 R4의 OpenAI Responses 기준은 2026-09-25 이전 설계 결정이다. 현재는 [Solar Pro 4의 1차 평가](../ai-developer/provider-evaluation.md)를 먼저 수행하고 Provider 구현을 확정한다. 따라서 모델·SDK·요청 형식·서버 Credential은 아직 최종 확정되지 않았다. 실제 전체 흐름에는 PostgreSQL과 GitHub OAuth App이 필요하다.
이를 테스트 fixture나 로그인 우회로 대체한 결과를 실제 서비스 검증으로 기록하지 않는다.
운영 환경 원문 잔존·실제 AI 정확도/지연·5명 사용성 검증은 구현 이후의 필수 검증이다.

## R7 — 보완 평가와 의존성 계획 정정

- FACT 최소 9개·SEM 12개·NORMAL 30개를 구분하고 사전 정답·분포·첫 요청 성공 정의를 Plan에 반영했다. 새로운 평가 결과가 아니라 사용자 보완 요청에 따른 설계다.
- 과거 설치에서 Better Auth 1.7.3과 Vitest 5.0.0의 peer 충돌이 확인됐다. Plan은 Vitest 4.x로 범위를 정정하며 정확한 patch·전체 engine/peer 검증·고정은 구현 승인 후 T001에서 수행한다. 설치 성공을 주장하지 않는다.


## R8 — 공개 인증 DTO와 API 문서 (2026-09-08)

- 기존 토큰 비노출 요구를 구체화한다. 공개 get-session은 customSession 및 대응 Client 타입으로 user.id/name·session.expiresAt만 반환하도록 설계한다. 라이브러리 기본 Session 객체를 그대로 반환하는 구현은 이 계약을 만족하지 않는다.
- 공개 인증 method/path는 로그인 시작·GitHub callback·세션 조회·로그아웃만 허용한다. SDK 프로토콜과 서버 내부 세션 검증은 유지한다.
- 로컬 OpenAPI 쿠키 이름은 설명용이며 실제 운영 속성·이름·SDK 응답 검증은 T007·T041·T042에 남긴다. 새 설치·실제 로그인 검증을 수행한 것은 아니다.
- 첫 Feature DTO·오류·버전/출처 계약을 Docs/api와 OpenAPI 3.1 JSON에 구체화했다. 후속 추천·설정은 DESIGN DRAFT로 구분한다.
- Sources: [Better Auth 세션 응답](https://better-auth.com/docs/concepts/session-management#customizing-session-response), [기본 사용](https://better-auth.com/docs/basic-usage), [GitHub](https://better-auth.com/docs/authentication/github), [쿠키](https://better-auth.com/docs/concepts/cookies), [OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.0.html). 공식 자료 확인과 실제 구현 검증을 구분한다.
