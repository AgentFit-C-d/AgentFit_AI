# HTTP and UI Contracts

모든 경로는 동일 출처의 Next.js 앱이 제공한다. API 응답은 Cache-Control: no-store.
프로젝트 API는 매 요청 DB 세션과 소유권을 검사하고 POST/PATCH/DELETE는 Origin도 검사한다.
비로그인은 401, 타인/없는 프로젝트는 구분되지 않는 404. 입력 본문에 ownerId를 허용하지 않는다.

상세 DTO·오류 매핑은 [팀 API 공통 규칙](../../../Docs/api/common.md)과 [첫 기능 상세](../../../Docs/api/01-project-analysis.md), 기계 판독 계약은 [OpenAPI 3.1](../../../Docs/api/openapi.phase1.json)에 함께 정의한다. 이 문서와 동일한 첫 Feature 계약이며 후속 API 초안은 포함하지 않는다.

## Authentication

`/api/auth/[...all]`은 Better Auth handler에 위임한다. GitHub만 활성화하고 로그인 scope는 user:email로 고정한다.
before hook은 `/sign-in/social`에서 github 외 provider와 caller scopes/idToken/accessToken/additionalParams·임의 callback URL을 거부한다.
`/get-access-token`, `/refresh-token`, `/link-social`, `/unlink-account`, `/account-info`, `/list-accounts`를 차단한다.
Account create/update hook은 token·expiry·password 필드를 **명시적 null**로 덮어쓴다.
로그인 callback은 `/api/auth/callback/github`, 성공 시 `/projects`. 로그아웃은 인증 라이브러리 POST로 세션을 폐기한다.
고정 baseURL/trustedOrigins, state·CSRF 검사를 유지한다. 브라우저 DTO에 Account/Session token을 포함하지 않는다.
공개 HTTP allowlist는 POST sign-in/social, GET callback/github, GET get-session, POST sign-out이다. 나머지 인증 경로는 기본 거부하며 서버 내부 세션 검증과 구분한다.
customSession 및 대응 Client 타입으로 GET get-session 응답을 { user: { id, name }, session: { expiresAt } } 또는 미로그인 null로 제한한다. 라이브러리 기본 Session 객체를 노출하지 않는다.
로그인·로그아웃·callback 프로토콜은 SDK가 처리한다. 인증 오류는 안전한 code/message 형식으로 처리하고 도메인 error envelope로 임의 포장하지 않는다. 저장소 장애는 503으로 구분한다.
성공/신규 사용자 callbackURL은 /projects, errorCallbackURL은 /?authError=github로 고정한다. 실제 쿠키·SDK·응답 검증은 T007·T041·T042에서 수행한다.

## Project API

| Method / path | Input | Success | Failure |
| --- | --- | --- | --- |
| GET /api/projects | 없음 | 200 `{ projects }`, 본인 목록만 | 401, 500/503 |
| POST /api/projects | JSON `{ name }` | 201 `{ project }` | 400/413/415/422, 401/403, 500/503 |
| GET /api/projects/:id | 없음 | 200 `{ project, confirmed, draft, latestAttempt }` | 401, 404, 500/503 |
| DELETE /api/projects/:id | JSON `{ confirmation: true }` | 204 | 400/413/415/422, 401/403, 404, 500/503 |
| POST /api/projects/:id/analysis | 아래 raw input | 200 `{ draft, attempt }` | 400/413/415/422, 401/403/404, 409/429, 500/502/503/504 |
| PATCH /api/projects/:id/profile | JSON `{ expectedVersion, data, draftId?, draftVersion? }` | 200 `{ project, confirmed }` | 400/413/415/422, 401/403/404, 409, 500/503 |

Project DTO는 id/name/version/timestamps를 제공한다. Profile DTO는 id/kind/data/sources/evidence/unknownFields/version/updatedAt을 제공한다.
Attempt DTO는 id/document/status/errorCode/startedAt/deadlineAt/finishedAt이며 document에는 최소 문서 정보만 포함한다. 상세의 confirmed/draft/latestAttempt는 없으면 null이고 키를 생략하지 않는다.
성공 응답은 필요한 필드만 구성하고 DB entity 전체를 그대로 직렬화하지 않는다.
JSON 요청은 65,536 bytes로 제한하고 추가 필드를 거부한다. 본문 초과는 413, 잘못된 값은 422 필드 오류다.
PATCH의 data는 10개 필드를 모두 포함한다. expectedVersion은 Project.version이며 draftId/draftVersion은 둘 다 제출하거나 생략한다.
초안 쌍을 제출하면 해당 DRAFT, 생략하면 기존 CONFIRMED와 비교한다. null은 UNKNOWN 및 빈 근거, 같은 알려진 값은 출처·유효 근거 유지, 변경/직접 작성한 알려진 값은 USER 및 빈 근거다. []도 알려진 값이다.
Project.version은 확인 저장마다 증가한다. DRAFT/CONFIRMED의 version은 각각 1부터 갱신마다 증가하며 확인 저장으로 DRAFT를 삭제하지 않는다. 오래된 버전은 409, 없는/타 프로젝트 draft는 동일한 404다.

## Analysis Input

- Content-Type: `application/pdf`, `text/markdown`, `text/plain` 중 하나.
  앞의 두 형식은 파일 입력, text/plain은 직접 입력이다.
- 선택 헤더 `X-Document-Name`은 파일명의 URI encoding이다. 디코딩·길이/제어문자·Secret 검사 후 최소 표시 이름만 저장한다.
- Content-Length는 빠른 사전 거부에만 사용한다. 실제 body 스트림의 누적 크기로 10,485,760 bytes를 검사한 뒤 파싱한다.
- PDF signature와 타입을 검사한다. Markdown·직접 입력은 UTF-8 fatal decode, code-point 100,000 포함 경계를 검사한다.
- PDF는 페이지 수를 추출 전에 확인한다. 하나라도 한도를 넘으면 자동 자르기 없이 거부한다.
- 같은 사용자의 진행 요청은 하나로 제한하고 서버 동시 분석 2건을 넘으면 429.
  같은 프로젝트의 진행 중 재요청은 409로 설명한다. body 읽기·PDF Worker 시작 전 동시 실행 슬롯을 원자적으로 확보하고 모든 종료 경로에서 반환한다. 사용자의 프로필 편집은 분석과 별개로 가능하다.
- 원문을 다시 제출해야 재분석할 수 있다. provider 재시도는 사용자의 명시적 새 요청으로만 수행한다.

## Errors

공통 응답: `{ error: { code, message, requestId, fields? } }`.
message는 제품이 정한 한국어 설명이며 외부 exception/message/body를 전달하지 않는다.

| Code | 의미 / 사용자 동작 |
| --- | --- |
| UNAUTHENTICATED / FORBIDDEN_ORIGIN | 로그인 또는 원래 사이트에서 재시도 |
| PROJECT_NOT_FOUND | 없는 프로젝트와 타인 프로젝트를 동일 처리 |
| INVALID_INPUT / UNSUPPORTED_DOCUMENT / INPUT_TOO_LARGE | 입력·유형·크기 수정 |
| EMPTY_DOCUMENT / UNREADABLE_DOCUMENT / PARTIAL_EXTRACTION | 읽을 수 있는 텍스트로 다시 입력 |
| SENSITIVE_INPUT | Credential 제거 후 다시 제출; 감지 문자열 자체는 표시하지 않음 |
| ANALYSIS_BUSY / RATE_LIMITED | 진행 결과 확인 또는 잠시 후 재시도 |
| AI_UNAVAILABLE / AI_INVALID_OUTPUT / ANALYSIS_TIMEOUT | 입력 재제출 또는 프로필 직접 작성·수정 |
| VERSION_CONFLICT | 최신 상태 불러오기, 현재 수정 입력은 화면에 보존 |
| STORAGE_UNAVAILABLE | 미저장 상태 표시, 입력을 보존해 저장 재시도 |
| INTERRUPTED | 저장된 Attempt의 중단 사유. GET 자체는 200이며 새 입력 요청 |
| INTERNAL_ERROR | 예상하지 못한 서버 오류는 500의 안전한 메시지 |

status code·error code 조합은 공통 규칙 및 OpenAPI에 고정하며 테스트에서 확인한다. 429는 Retry-After 초를 제공하고 도메인 응답은 X-Request-Id를 제공한다. 요청 식별자는 원문·사용자 입력을 포함하지 않는다.

## UI Contract

- `/`: AgentFit 설명, GitHub 로그인, 필요한 권한과 준비 상태. 인증 실패를 설명한다.
- `/projects`: 본인 프로젝트 목록, 빈 상태, 이름 입력, 생성 중·실패 상태, 로그아웃.
- `/projects/:id`: 입력 → 분석 → 검토·저장 흐름. 저장된 확인 프로필과 새로운 초안을 분리한다.
  제한·PDF 텍스트 범위·원문 보관·외부 AI 전송/보관 고지를 분석 시작 전에 표시한다.
- 필드마다 미정과 값/명시적 없음을 구분한다. 근거 위치·문서/사용자 출처를 표시한다.
  위치 정보는 원문 재열람이 아님을 설명하고 처리 후에는 사용자가 가진 원본으로 확인하도록 안내한다. 서버에 인용문을 계속 보관하지 않는다.
  null이 남아도 확인 저장 가능하며, 저장 실패 때 편집 상태를 지우지 않는다.
- AI 실패 시 재입력 기반 재시도와 직접 작성·수정 동작을 제공한다.
- 프로젝트 삭제는 이름과 함께 제거될 데이터를 표시하는 확인 UI를 거친다. 취소는 무변경.
- 진행·성공·실패는 텍스트로 안내하고 live region, label, 키보드 focus를 제공한다.
- 설치·환경 verified 등의 상태나 아직 구현하지 않은 추천 메뉴를 완료 기능처럼 표시하지 않는다.
