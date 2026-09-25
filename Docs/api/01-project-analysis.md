# 1단계 API — 프로젝트·문서 분석

> 기존 Feature 001-project-document-analysis의 설계 계약 구체화 · 2026-09-08
>
> 구현·실제 호출 검증 전. 기계 판독 형식은 [OpenAPI 3.1 JSON](openapi.phase1.json).
>
> 2026-09-25 변경: 공개 프로젝트 API의 구현 주체는 Spring Boot이며 내부 AI 분석은 FastAPI가 맡는다. 아래 공개 DTO·경로는 서비스 분리 후 재검토가 필요하다. FastAPI 성공만으로 `200 draft`를 반환하지 않고 Spring Boot의 검증·저장 성공을 확인한다. 실패 건의 LLM 원본 응답은 진단용으로 최대 7일 보관하며 공개 API에 포함하지 않는다.

## 1. 담당과 경로

A가 API·DB·인증·상태를 통합하고, AI가 추출·Provider·필드 의미, Frontend가 입력·표시·편집·복구를 연결한다. Designer는 상태·고지·사용성을 확인한다.

| Method | Path | 목적 | 성공 |
| --- | --- | --- | --- |
| GET | /api/auth/get-session | 제한된 공개 세션 | 200 객체 또는 null |
| GET | /api/projects | 본인 프로젝트 목록 | 200 projects |
| POST | /api/projects | 프로젝트 생성 | 201 project |
| GET | /api/projects/{projectId} | 프로젝트·초안·확인값·최근 분석 | 200 상세 |
| DELETE | /api/projects/{projectId} | 프로젝트 및 연결 데이터 삭제 | 204 |
| POST | /api/projects/{projectId}/analysis | 입력·추출·분석·초안 저장 | 200 draft·attempt |
| PATCH | /api/projects/{projectId}/profile | 사용자 확인 Profile 저장 | 200 project·confirmed |

GitHub 로그인 시작·로그아웃·callback은 [공통 인증 경계](common.md)를 따른다.
모든 도메인 오류의 코드·상태는 공통 규칙과 OpenAPI를 함께 사용한다.

## 2. 공개 DTO

| DTO | 필드 | 규칙 |
| --- | --- | --- |
| Project | id, name, version, createdAt, updatedAt | ownerId·analysisGeneration 비공개. 이름 trim 후 1–100 code points |
| Profile | id, kind, data, sources, evidence, unknownFields, version, updatedAt | kind DRAFT/CONFIRMED, version 1 이상 |
| DocumentSummary | id, kind, displayName, byteSize, characterCount, pageCount, createdAt | 원문 없음. 미확인 count는 null. 이름은 정제된 최대 200 code points |
| AnalysisAttempt | id, document, status, errorCode, startedAt, deadlineAt, finishedAt | PROCESSING/SUCCEEDED/FAILED. document는 위 최소 정보 |
| PublicSession | user.id/name, session.expiresAt | Token·Account·원본 Session 제외. 미로그인은 null |

Profile.data는 다음 10개 필드를 모두 포함한다.

| 필드 | 타입 |
| --- | --- |
| project_name, project_type, domain, database, deployment | string 또는 null |
| frontend, backend, ai, features, external_integrations | string[] 또는 null |

각 문자열은 최대 200 code points, 배열은 최대 30개다. 빈 문자열·공백만 있는 문자열은 미정 대신 사용하지 않는다.
배열 null은 미정, []는 명시적 없음이다. 전체 JSON 요청 65,536 bytes 제한도 함께 적용된다.

sources는 10개 필드별 DOCUMENT/USER/UNKNOWN, evidence는 10개 필드별 위치 배열, unknownFields는 null인 필드명을 서버가 계산한 배열이다.
evidence 항목은 documentId와 page 또는 start/end를 가진다. page는 1부터, start/end는 추출 전체 텍스트 기준 code-point 위치이며 시작 포함·끝 제외다. start/end는 쌍이고 end > start여야 한다.
DOCUMENT의 알려진 값에는 유효 근거가 하나 이상 있어야 한다. USER·UNKNOWN에는 원문 근거 배열을 남기지 않는다. 위치에서 원문을 재조회할 수는 없다.

## 3. 프로젝트 생성·목록·상세

### POST /api/projects

Content-Type은 application/json이다. 요청과 응답 예시는 다음과 같다.

요청:

```json
{
  "name": "운동 기록"
}
```

201 응답:

```json
{
  "project": {
    "id": "prj_example_01",
    "name": "운동 기록",
    "version": 0,
    "createdAt": "2026-09-08T00:00:00Z",
    "updatedAt": "2026-09-08T00:00:00Z"
  }
}
```

400은 JSON 문법, 422는 name·추가 필드·민감 입력 오류다. 동일한 이름의 별도 프로젝트를 자동 병합하지 않는다.
자동 생성 재시도를 하지 않으며 응답이 유실되면 목록을 확인한다.

### GET /api/projects

입력·query 없음. 본인 프로젝트를 updatedAt 내림차순, 같은 시각이면 id 오름차순으로 반환한다.
첫 단계에는 페이지네이션·검색·팀 공유 필터가 없다. 빈 목록은 `{ "projects": [] }`다.

### GET /api/projects/{projectId}

응답의 project·confirmed·draft·latestAttempt 키는 항상 존재한다. 아직 없는 Profile/Attempt는 null이다.
공개 전체 예시는 OpenAPI의 ProjectDetailResponse를 따른다.

- confirmed와 draft가 둘 다 있으면 별개로 표시한다.
- latestAttempt는 최근 분석 시도다. 최신 시도가 실패해도 이전에 저장된 draft·confirmed는 삭제하지 않는다.
- 입력 검증에서 거부되어 Attempt를 만들지 않은 요청도 있다. 현재 제출 오류와 이전 latestAttempt를 같은 요청으로 오인하지 않는다.
- PROCESSING이면 finishedAt/errorCode는 null, SUCCEEDED이면 finishedAt이 있고 errorCode는 null, FAILED이면 finishedAt과 안전한 errorCode가 있다.
- deadline이 지난 진행 시도는 조회/새 요청 시 FAILED·INTERRUPTED로 정리한다. 이를 원문 자동 재분석으로 복구하지 않는다.

## 4. 문서 분석

### POST /api/projects/{projectId}/analysis

| 입력 | Content-Type | body |
| --- | --- | --- |
| PDF 파일 | application/pdf | 파일 원본 bytes |
| Markdown 파일 | text/markdown | UTF-8 파일 내용 |
| 직접 텍스트 | text/plain | UTF-8 텍스트 |

multipart/form-data·base64 JSON·URL·documentId 입력을 사용하지 않는다.
파일 입력은 선택적으로 X-Document-Name에 URI encoding한 표시 이름을 보낼 수 있다. TEXT는 생략한다. 서버가 디코딩·길이·제어 문자·Secret을 검사한다.

검사 순서와 제한:

1. 세션·Origin·소유권을 확인한다.
2. Content-Type·헤더를 검사하고 body 읽기 전에 동시 실행 슬롯을 원자적으로 확보한다. 같은 프로젝트 진행 중 재요청은 409, 사용자 진행 1건·서버 전체 2건 초과는 429다.
3. Content-Length만 믿지 않고 실제 스트림으로 10,485,760 bytes와 기본 형식·이름을 검사한다. 사전 거부 후 슬롯을 반환한다.
4. PDF 최대 100쪽, 추출·직접 텍스트 최대 100,000 code points를 포함 경계로 검사한다. 텍스트는 UTF-8 fatal decode를 사용한다.
5. 잠금·손상·빈 내용·부분 추출을 구분한다. PDF의 텍스트/비텍스트 페이지 혼재 처리는 현재 Plan의 거부 정책을 따른다.
6. 검증된 DRAFT·최소 Attempt·Audit 저장 후 200으로 반환한다. 성공·실패·취소를 포함한 모든 종료에서 원문을 보관하지 않고 슬롯을 반환한다.

합성 직접 입력 예시:

```text
운동 기록은 웹 서비스이다. 프론트엔드는 React, 백엔드는 Node.js로 확정했다. DB와 배포는 미정이다.
```

200 응답은 draft·attempt를 포함한다. 위 문서의 DB·배포는 null, project_name과 확정 기술은 근거와 함께 추출한다.
응답 예시는 [OpenAPI의 AnalysisResponse](openapi.phase1.json)에 있다. profile.sources·evidence·unknownFields는 클라이언트 입력이 아니다.

서버 요청 전체 기한은 현재 Plan의 60초 예산을 따른다. PDF Worker 15초·AI 40초와 저장/응답 시간을 배분하며 SDK 자동 재시도는 끈다.
SC-008의 사용자 관측 시간은 제출 동작부터 결과/명시적 실패 표시까지 측정하며, 서버 Attempt 시각만으로 화면 응답 시간을 대체하지 않는다.

취소·연결 끊김을 감지하면 작업·Worker 중단을 시도하고 이미 커밋된 결과를 되돌렸다고 단정하지 않는다. 복귀 시 GET 상세로 실제 상태를 확인한다.
취소 전용 endpoint·작업 큐는 이 계약에 추가하지 않는다. 실제 신호 전달·중단·잔존 검증은 T020·T023·T034에서 수행한다.

## 5. Profile 확인·직접 작성

### PATCH /api/projects/{projectId}/profile

부분 필드 patch가 아니라 **data의 10개 필드를 모두 제출**하는 계약이다. 미정도 null로 포함한다.
서버 생성 항목인 kind·sources·evidence·unknownFields·ownerId를 보내면 거부한다.

초안 확인 요청:

```json
{
  "expectedVersion": 0,
  "data": {
    "project_name": "운동 기록",
    "project_type": "웹 서비스",
    "domain": null,
    "database": null,
    "deployment": null,
    "frontend": [
      "React"
    ],
    "backend": [
      "Node.js"
    ],
    "ai": null,
    "features": null,
    "external_integrations": null
  },
  "draftId": "prof_draft_example_01",
  "draftVersion": 1
}
```

200 응답은 `{ project, confirmed }`이며 Project.version은 1 증가하고 CONFIRMED가 갱신된다.
DRAFT는 확인값과 별개다. 확인 저장이 DRAFT를 자동 삭제하거나 다음 분석의 버전을 초기화하지 않는다.

출처·근거 계산:

1. draftId/draftVersion은 둘 다 보내거나 둘 다 생략한다. 다른 프로젝트·없는 draft는 404 PROJECT_NOT_FOUND, 오래된 같은 프로젝트 draft는 409 VERSION_CONFLICT다.
2. 쌍이 있으면 해당 DRAFT를 비교 기준으로, 없으면 기존 CONFIRMED를 기준으로 삼는다. 둘 다 없으면 직접 작성이다.
3. data 값이 null이면 UNKNOWN, 근거 []다.
4. 기준의 알려진 값과 구조적으로 같으면 기존 DOCUMENT/USER 출처와 유효 근거를 유지한다. 알려진 빈 배열 []도 값으로 비교한다.
5. 기준과 다른 알려진 값은 USER로 바꾸고 원문 근거를 제거한다. 비교 기준 없는 직접 작성의 알려진 값도 USER다.
6. unknownFields는 null 필드로 재계산한다. expectedVersion·draft version 검사와 저장·Audit는 같은 트랜잭션에서 일관되게 처리한다.

초안이 없어도 expectedVersion과 전체 data만 보내 직접 작성할 수 있다.
수정 저장 실패 시 현재 편집값을 유지한다. 409이면 상세 재조회·사용자 재검토를 거치며 새 버전으로 자동 덮어쓰지 않는다.

## 6. 프로젝트 삭제

### DELETE /api/projects/{projectId}

```json
{
  "confirmation": true
}
```

본인 프로젝트와 Profile·Document 최소 정보·Attempt·Audit를 함께 제거하고 204로 응답한다.
Body가 없거나 confirmation=false면 삭제하지 않는다. User·인증 Session은 프로젝트 삭제와 별개다.
이미 삭제됐거나 타인 프로젝트는 404이며, 204 body를 JSON으로 파싱하지 않는다.

## 7. 화면 연결과 인수 확인

| 화면 동작 | 호출 | 필수 확인 |
| --- | --- | --- |
| 첫 로그인 상태 | GET get-session, 보호 API | null·401·저장소 장애 구분, Token 없음 |
| 프로젝트 만들기·재접속 | POST projects → GET 목록/상세 | 저장된 ID·버전·값 일치 |
| 입력·분석 | POST analysis → 필요 시 GET 상세 | raw 형식·한도·초안 저장·기존 확인값 보존 |
| 수정·확인 저장 | PATCH profile → GET 상세 | Project/draft 버전·출처·미정·동시성 |
| 실패·취소 | 안전한 오류 + GET 상세 | 재입력 재시도·직접 작성·현재 편집값 보존 |
| 삭제 | 확인 → DELETE | 204·cascade·지연 복원 차단 |

기계 스키마로 구조를 검사한 것과 실제 API가 작동한 것은 별개다. 실제 DB·GitHub·Provider·브라우저·운영 보관 검증을 기존 T001–T046에 따라 수행한다.

[API 목차](README.md) · [공통 규칙](common.md) · [Feature 계약](../../specs/001-project-document-analysis/contracts/http.md) · [데이터 모델](../../specs/001-project-document-analysis/data-model.md)
