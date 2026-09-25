# AgentFit API 공통 규칙

> 설계 기준: 2026-09-08 · 구현·실제 호출 검증 전
>
> 1단계는 기존 문서 분석 계약의 구체화, 2·3단계는 후속 Feature로 전개할 설계 초안이다.

## 1. 전송·접근·명명

- 경로는 동일 출처 웹 앱의 `/api`로 시작한다. 별도 공개 API 서버·Bearer 인증을 추가하지 않는다.
- 보호 API는 매 요청 DB 세션과 소유권을 검사한다. 비로그인은 401, 타인 프로젝트와 없는 프로젝트는 같은 404다.
- 하위 객체는 반드시 URL의 프로젝트에 속해야 한다. 다른 프로젝트의 draft·recommendation·preview·approval ID로 접근을 넓힐 수 없다.
- 상태 변경의 Origin은 정확한 서비스 출처와 일치해야 하며 누락·불일치를 403으로 거부한다. OAuth callback은 외부 탐색 요청이므로 라이브러리의 state·CSRF 검증으로 별도 처리한다.
- JSON 요청/응답은 UTF-8이다. 일반 JSON 요청 본문 한도는 65,536 bytes이며 추가 필드를 거부한다. 후속 설정 API의 더 큰 한도는 해당 초안에 별도 명시한다.
- 성공·실패 응답에 `Cache-Control: no-store`를 사용한다. 도메인 API는 서버가 만든 `X-Request-Id`를 제공한다.
- ID는 불투명 문자열, 날짜는 UTC ISO 8601, DTO 외곽 필드명은 camelCase다. 기존 Profile `data`의 snake_case 필드명은 유지한다.
- 필수 nullable 필드는 값이 없을 때 `null`로 보낸다. 빈 배열과 null을 같은 값으로 변환하지 않는다.
- 요청에 ownerId·서버 상태·검증 성공·출처·Audit 내용을 임의로 주입할 수 없다. 허용된 입력 필드만 받는다.
- API 예시의 ID·문서·버전·시각은 합성 데이터이며 실제 저장/호환성 검증 결과가 아니다.

## 2. GitHub 로그인과 세션

인증은 Better Auth의 SDK·handler에 위임하되 AgentFit의 공개 응답·입력 제한을 적용한다.
로그인은 GitHub 식별 용도이고 scope는 `user:email`로 고정한다. 저장소 권한·다른 provider·idToken/accessToken 로그인·임의 scopes/additionalParams를 받지 않는다.

| 사용자 동작 | HTTP 경계 | 팀의 사용 규칙 |
| --- | --- | --- |
| GitHub 로그인 시작 | POST /api/auth/sign-in/social | SDK signIn.social 사용. provider=github, 성공/신규 사용자 목적지는 /projects, 실패 목적지는 /?authError=github로 고정 |
| GitHub callback | GET /api/auth/callback/github | SDK 내부 OAuth 교환·state 검증. Frontend에서 직접 조립·재호출하지 않음 |
| 현재 세션 확인 | GET /api/auth/get-session | 200 안전한 PublicSession 또는 미로그인일 때 200 null |
| 로그아웃 | POST /api/auth/sign-out | SDK signOut으로 서버 세션 폐기 후 화면 이동. 다음 보호 요청은 401 |

로그인·로그아웃·callback의 프로토콜 응답은 인증 SDK가 처리한다. 도메인 API의 응답 envelope로 임의 포장하지 않는다.
로그인 목적지·에러 목적지를 요청자가 임의 외부 URL로 바꿀 수 없도록 서버에서도 검사한다.

세션의 공개 성공 응답은 아래로 제한한다.

```json
{
  "user": { "id": "user_example_01", "name": "예시 사용자" },
  "session": { "expiresAt": "2026-09-09T00:00:00Z" }
}
```

Account·Session 엔티티를 통째로 반환하지 않는다. session token·provider token·계정 토큰·IP·User-Agent·불필요한 이메일/이미지는 공개 DTO에 넣지 않는다.
Better Auth의 `customSession`과 대응 client 타입으로 이 계약을 적용한다. 이 형태는 **AgentFit이 구현해야 할 제한 응답**이며 라이브러리 기본 응답이 안전하게 축약된다는 뜻이 아니다.

공개 인증 경로는 위 네 동작의 method/path만 허용한다. account·token 조회/갱신·연결, list-sessions·revoke-session 등의 다른 인증 API를 브라우저에 자동 개방하지 않는다.
서버 내부 세션 검증과 HTTP 공개 경로 제어를 분리한다. allowlist가 서버 내부의 정상 세션 검증을 막으면 안 된다.

인증 오류는 SDK에 맞는 안전한 `{ "code": "...", "message": "..." }` 형태를 유지한다. A가 상태·코드·한국어 안내를 검토해 고정하고 Frontend는 알려진 코드 또는 일반 로그인 실패 안내로 처리한다.
원본 Provider 메시지·콜백 query·token을 그대로 화면에 반영하지 않는다. 저장소 장애를 '로그아웃됨'으로 처리하지 않는다.

인증 쿠키는 라이브러리가 HttpOnly로 관리하고 운영에서는 Secure 속성을 사용한다. 쿠키 캐시는 비활성화하고 DB 세션을 검사한다.
OpenAPI의 `better-auth.session_token`은 로컬 기본 이름 설명이다. 운영의 실제 쿠키 이름·속성과 SDK 응답 적합성은 T007·T041·T042에서 검증·동기화한다. Swagger 예시를 위해 실제 쿠키·Token을 문서에 붙이지 않는다.

근거: Better Auth는 세션 응답의 사용자/세션 객체를 사용자 정의할 수 있다. GitHub 로그인과 signOut은 해당 SDK 경계를 사용한다. [세션 응답 공식 문서](https://better-auth.com/docs/concepts/session-management#customizing-session-response), [GitHub 로그인](https://better-auth.com/docs/authentication/github), [기본 사용](https://better-auth.com/docs/basic-usage), [쿠키](https://better-auth.com/docs/concepts/cookies). 2026-09-08 확인이며 실제 설치·호출 검증과 구분한다.

## 3. 도메인 API 오류

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "프로젝트 이름을 확인해 주세요.",
    "requestId": "request_example_01",
    "fields": { "name": ["공백을 제외한 이름을 입력해 주세요."] }
  }
}
```

`fields`는 선택 필드이며 키는 name·data.database 같은 입력 경로, 값은 설명 문자열 배열이다. 사용자가 입력한 민감 값·Provider 원본 오류·stack trace는 포함하지 않는다.
Frontend는 code로 행동을 선택하고 message는 안내로 표시한다. 204 응답에는 JSON body가 없다.

| HTTP | code | 의미 |
| --- | --- | --- |
| 400 | INVALID_INPUT | 잘못된 JSON·헤더 인코딩·요청 문법 |
| 401 | UNAUTHENTICATED | 로그인 필요·만료 |
| 403 | FORBIDDEN_ORIGIN | 상태 변경 요청의 Origin 누락·불일치 |
| 404 | PROJECT_NOT_FOUND | 없는 프로젝트·타인 프로젝트를 동일 처리 |
| 413 | INPUT_TOO_LARGE | JSON·raw body·문자·페이지 한도 초과 |
| 415 | UNSUPPORTED_DOCUMENT | 지원하지 않는 Content-Type·파일 유형 |
| 422 | INVALID_INPUT | 필수/추가 필드·값 범위·confirmation·draft 필드 쌍 검증 실패 |
| 422 | EMPTY_DOCUMENT | 비어 있는 내용 |
| 422 | UNREADABLE_DOCUMENT | 잠금·손상·잘못된 UTF-8 등 읽을 수 없는 내용 |
| 422 | PARTIAL_EXTRACTION | 일부 추출 의심·텍스트 없는 페이지 혼재 |
| 422 | SENSITIVE_INPUT | 식별한 Credential·Secret 제거 필요 |
| 409 | ANALYSIS_BUSY | 같은 프로젝트에 진행 중 분석 존재 |
| 409 | VERSION_CONFLICT | Project 또는 선택한 draft 버전 불일치 |
| 429 | RATE_LIMITED | 사용자 1건·서버 2건 동시 분석 한도 |
| 502 | AI_UNAVAILABLE | 외부 AI 오류·거절·외부 요청 제한 |
| 502 | AI_INVALID_OUTPUT | 외부 AI 응답 구조·값 검증 실패 |
| 503 | AI_UNAVAILABLE | AI 실행 준비·의존 서비스 사용 불가 |
| 503 | STORAGE_UNAVAILABLE | DB 조회·저장 사용 불가 |
| 504 | ANALYSIS_TIMEOUT | 분석 전체 기한 초과 |
| 500 | INTERNAL_ERROR | 예상하지 못한 서버 오류. 원본 예외 노출 금지 |

`INTERRUPTED`는 연결 중단·기한 만료 복구로 저장한 Attempt.errorCode다. 상세 조회 자체는 200이며, 이미 끊긴 연결에 가상의 HTTP 응답을 보냈다고 기록하지 않는다.
`UNSUPPORTED_DOCUMENT`는 첫 단계의 잘못된 Content-Type에도 사용한다. 후속 JSON 전용 API는 415 `UNSUPPORTED_MEDIA_TYPE`로 구체화할 수 있으나 첫 단계의 기존 코드와 섞지 않는다.

에러 순서는 세션·출처·소유권을 먼저 판정한 뒤 도메인 입력·충돌·외부 호출을 진행한다. 지나치게 큰 본문은 전송 계층에서 먼저 중단할 수 있으나 프로젝트 내용·존재 여부를 추가로 노출하지 않는다.
같은 프로젝트 분석 중이면 409 ANALYSIS_BUSY, 다른 프로젝트를 포함한 사용자 동시 한도 또는 서버 전체 한도이면 429 RATE_LIMITED다. 429는 Retry-After의 최소 대기 초를 제공한다.

## 4. 버전·재시도·화면 상태

- Project.version은 생성 시 0이며 확인 Profile 저장 성공마다 증가한다. 분석 자체는 별도 generation과 draft.version을 사용한다.
- Profile.version은 각 DRAFT/CONFIRMED 기록의 서버 버전이며 최초 저장 1, 갱신마다 증가한다. 숫자 자체를 콘텐츠 hash로 취급하지 않는다.
- 확인 저장의 expectedVersion은 **Project.version**이다. draft를 확인하는 경우 draftId/draftVersion도 쌍으로 검증한다.
- 409이면 현재 편집값을 보존하고 최신 상세를 조회한다. 최신 version으로 바꿔 같은 데이터를 자동 덮어쓰지 않는다.
- 분석·프로젝트 생성·확인 저장의 네트워크 오류에 자동 POST/PATCH 재전송을 하지 않는다. 먼저 GET으로 결과를 확인하고 필요한 경우 사용자가 새 요청을 선택한다.
- 서버에서 요청 결과가 커밋됐지만 응답이 유실될 수 있다. 화면의 네트워크 오류를 곧바로 '서버에 저장 안 됨'으로 단정하지 않는다.
- 분석은 raw 입력을 받는 동기 요청이다. 202·작업 큐·SSE·WebSocket 계약을 임의로 추가하지 않는다. 분석 중 재접속은 프로젝트 상세의 latestAttempt로 복원한다.
- 처리 종료 후 원문 재시도는 재입력이 필요하다. 원문 다운로드 API·documentId만으로 재분석하는 API는 제공하지 않는다.

## 5. DTO와 내부 실행의 구분

DTO는 공개 계약이며 Prisma·Provider의 전체 객체를 직렬화하지 않는다.
세션 검증, PDF Worker, AI Provider, Capability 도출, 권한 평가, 템플릿 합성은 모듈 내부의 계약이다. 브라우저가 임의 Prompt·도구 실행·권한 평가를 요청하는 범용 endpoint를 만들지 않는다.

원문·추출문·근거 인용·기존 설정 입력은 처리 종료 후 보관하지 않는다. 최소 메타데이터·Profile·후속 최소 이력은 본인만 접근하고 프로젝트 삭제에 연동한다.
실제 서버·Provider·운영 호스트의 보관 검증은 별도 수행한다.

[API 목차](README.md) · [첫 기능 상세](01-project-analysis.md) · [기존 HTTP 계약](../../specs/001-project-document-analysis/contracts/http.md)
