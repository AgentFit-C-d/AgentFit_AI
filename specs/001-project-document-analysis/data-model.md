# Data Model: Project Document Analysis

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Authentication

Better Auth 호환 모델을 Prisma로 관리한다. 식별자와 timestamp는 서버가 생성한다.

| Entity | 핵심 필드·관계 | 제약 |
| --- | --- | --- |
| User | id, name, email, emailVerified, image?, createdAt, updatedAt | email unique. image는 보관하지 않음 |
| Session | id, userId, token, expiresAt, ipAddress?, userAgent?, timestamps | token unique, User FK. cookie cache 없음. IP·UA 보관 안 함 |
| Account | id, userId, providerId, accountId, scope?, nullable token/expiry/password fields, timestamps | providerId+accountId unique, GitHub만 허용. token·expiry·password는 create/update 훅에서 null |
| Verification | id, identifier, value, expiresAt, timestamps | 인증 라이브러리 내부 용도. LLM·일반 API에 노출하지 않음 |

Provider token과 Session token을 구분한다. 로그인 후 GitHub token은 저장하지 않지만,
접근 제어에 필요한 세션 정보는 인증 라이브러리의 서버 저장소에서 관리한다.
Auth User/Session은 프로젝트 삭제와 별개이며 이번 Feature에 계정 삭제 기능은 포함하지 않는다.

## Project Domain

| Entity | 필드 | 관계·제약 |
| --- | --- | --- |
| Project | id, ownerId, name, version, analysisGeneration, createdAt, updatedAt | ownerId→User, name trim 후 1–100 code points, owner+updatedAt index |
| ProjectDocument | id, projectId, kind, displayName, byteSize, characterCount?, pageCount?, createdAt | kind=PDF/MARKDOWN/TEXT. 원문·추출문·인용문 컬럼 없음 |
| AnalysisAttempt | id, projectId, documentId, generation, status, errorCode?, startedAt, deadlineAt, finishedAt? | status=PROCESSING/SUCCEEDED/FAILED, 프로젝트별 현재 generation만 결과 반영 |
| ProjectProfile | id, projectId, kind, data, sources, evidence, unknownFields, version, updatedAt | kind=DRAFT/CONFIRMED, unique(projectId, kind), 값·출처 JSON 구조는 공통 schema로 검증 |
| AuditEvent | id, projectId, actorId, attemptId?, event, outcome, createdAt | 사건·결과는 enum. 원문·입력·exception·secret metadata 없음 |

ProjectDocument/AnalysisAttempt/ProjectProfile/AuditEvent의 projectId는 Project로 연결되고
프로젝트 삭제 시 cascade 제거한다. attemptId는 추적 식별자이며 임의 객체 metadata를 저장하지 않는다.
Document 삭제는 개별 기능으로 노출하지 않는다. Project 하위 객체의 독립 공개 접근 경로는 없다.

## Project Profile Value Contract

| 필드 | 값 |
| --- | --- |
| project_name, project_type, domain, database, deployment | string 또는 null |
| frontend, backend, ai, features, external_integrations | string[] 또는 null |

- null은 미정, 빈 배열은 명시적으로 확인한 '없음'이다. 두 상태를 같은 값으로 변환하지 않는다.
- 알려진 문자열은 공백만 있을 수 없으며 1–200 code points, 배열은 최대 30개 항목이다. 경계 초과는 설명과 함께 거부한다.
- unknownFields는 값이 null인 필드에서 서버가 계산하며 클라이언트·LLM 값을 믿지 않는다.
- sources는 필드별 DOCUMENT/USER/UNKNOWN. 사용자 변경 필드는 USER로 바꾸고 오래된 근거 위치를 제거한다.
- evidence는 DOCUMENT 필드별 문서 id, 페이지 또는 code-point start/end의 목록이다.
  인용문·문서 원문은 포함하지 않는다. 시작 포함·끝 제외이며 추출 시의 텍스트를 기준으로 한다.
- Provider 중간 응답의 evidence quote는 원문에 실제 존재하는지 검사한다.
  추출값은 원문 표현을 사용하며 해당 근거에 값이 없거나 근거가 없으면 필드를 null로 만든다.
  부정·후보·시간·다른 대상·상충·문맥 제한을 함께 판단하며 문자열 존재만으로 확정하지 않는다.
  정규화·동의어로 Capability를 확장하는 작업은 후속 Feature의 역할이다.

## State Transitions

1. 프로젝트 생성: version=0, analysisGeneration=0, 프로필 없음.
2. 분석 시작: 소유권·세션·입력 경계 확인 후 generation 증가, Document 최소 metadata와 PROCESSING Attempt 생성.
3. 분석 성공: 소유권·프로젝트 존재·현재 generation·PROCESSING 조건을 다시 확인한 트랜잭션에서
   DRAFT 갱신, Attempt SUCCEEDED, Audit 추가. CONFIRMED는 변경하지 않는다.
4. 분석 실패: 존재하는 해당 Attempt만 FAILED로 갱신하고 안전한 errorCode를 기록한다.
   원문을 저장하거나 이전 프로필을 삭제하지 않는다.
5. 프로필 확인 저장: expectedVersion과 Project.version이 같을 때만 CONFIRMED 저장 및 version 증가.
   DRAFT를 확인하는 경우 draft id/version도 검증한다. null이 남아도 확인 저장은 가능하다.
6. 수동 작성: AI 성공과 독립적으로 CONFIRMED를 저장하고 변경값은 USER 출처로 기록한다.
7. 삭제: owner 조건으로 Project 삭제 후 cascade. 지연 결과는 FK/조건 검증에서 거부되며 upsert로 Project를 재생성하지 않는다.
8. 중단 복구: deadline이 지난 PROCESSING은 조회·새 요청 시 FAILED/INTERRUPTED로 정리한다.
   원문이 없으므로 자동 재실행하지 않는다.

외부 AI 호출 중 DB lock을 유지하지 않는다. version·generation 갱신과 프로필/Audit 저장은
짧은 트랜잭션에 묶고 충돌은 409로 반환한다. 프로젝트 소유자 id를 요청 본문에서 받지 않는다.

## Public DTO and Save Invariants

DB Entity와 공개 DTO를 구분한다. [HTTP 상세](../../Docs/api/01-project-analysis.md)와 [OpenAPI](../../Docs/api/openapi.phase1.json)에 실제 필드·nullable·형식을 정의한다.
PublicSession은 user.id/name, session.expiresAt만 반환하며 토큰·IP·UA·이메일·이미지를 노출하지 않는다.
Profile의 data/sources/evidence는 10개 필드를 모두 포함한다. null 값은 UNKNOWN·빈 근거, USER도 빈 근거이며 DOCUMENT의 알려진 값에는 유효 위치가 필요하다.
근거 start/end는 쌍이며 0 <= start < end <= 처리 당시 텍스트 code-point 수다. page는 해당 문서의 유효 페이지 안에 있어야 한다.
확인 요청의 draftId/draftVersion 쌍이 있으면 해당 초안을, 없으면 기존 확인 Profile을 비교 기준으로 삼는다.
구조적으로 같은 알려진 값([] 포함)은 기존 출처·유효 근거를 보존하고 변경값/직접 작성값은 USER로 만든다. null은 언제나 UNKNOWN이다.
Project.version은 확인 저장 시 증가한다. Profile.version은 DRAFT/CONFIRMED 각각 처음 1이며 갱신마다 증가한다. 확인 저장으로 초안을 삭제하거나 버전을 초기화하지 않는다.
Attempt의 PROCESSING은 finishedAt/errorCode=null, SUCCEEDED는 finishedAt이 있고 errorCode=null, FAILED는 finishedAt과 안전한 errorCode가 있다.
공개 Attempt의 document는 최소 DocumentSummary이며 원문 조회 권한/URL을 제공하지 않는다.
정상 입력 경계 검사 뒤 Attempt를 생성하되 Worker 실행 슬롯은 body 읽기 전에 확보한다. 사전 거부로 Attempt가 없는 오류와 이전 latestAttempt를 구분한다.

## Retention

업로드 원문·추출문·근거 인용문과 정상 분석의 전체 AI 응답은 처리 후 보관하지 않는다.
실패한 분석에서 수신된 LLM 원본 응답만 별도 진단 데이터로 최대 7일 보관하며, 프로젝트 삭제 시에도 제거한다. 이 진단 데이터는 공개 Profile·DocumentSummary·Audit·일반 로그에 포함하지 않는다. PostgreSQL 접근과 만료 삭제는 Spring Boot가 소유한다. 진단 테이블의 정확한 schema·암호화·권한·만료 작업은 서비스 간 계약 설계에서 고정한다.
외부 Provider의 보관과 운영 환경의 dump/spooling은 [Plan](plan.md)의 별도 검증 조건이다.
