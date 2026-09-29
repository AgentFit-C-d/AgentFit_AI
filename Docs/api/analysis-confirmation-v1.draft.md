# 분석 확인 필요 응답 인계안 (초안)

상태: **Full Stack A·Frontend 합의 전**. 현재 [1단계 공개 API](01-project-analysis.md)와 OpenAPI에는 아래 공개 필드·상태가 없다. 이 문서는 AI 내부 결과를 저장·표시·확인하는 데 필요한 결정안을 정리하며 기존 공개 계약을 자동 변경하지 않는다.

## AI 내부 호출

- FastAPI에서 `AGENTFIT_ANALYSIS_MODE=recoverable-solar`를 명시적으로 설정한다. 기본값 `default`는 계속 일반 Solar 분석이다.
- 복구 모드를 호출하는 Spring은 기존 Bearer 토큰과 함께 `X-AgentFit-Analysis-Contract: confirmation-v1`을 정확히 한 번 보낸다. 누락·중복·다른 값은 body 읽기 전에 `428 CONFIRMATION_CONTRACT_REQUIRED`다. 이 헤더는 Spring 구현 검증을 대체하지 않는다.
- `POST /internal/v1/analyze`의 `outcome`은 `complete`, `needs_confirmation`, `failed`다. `needs_confirmation`에는 재검증 가능한 `profile`, 10개 필드의 `fieldStates`, 안전한 `questions`, 안전 오류 코드가 포함된다.
- `suggested`는 근거 구조가 검증된 값이지만 사용자 확인 전 확정이 아니다. `unknown`은 null이며 편집 가능하다. `unresolved`는 null이며 해당 질문이 하나 있어야 한다. `suggested`의 `REVIEW_UNAVAILABLE` 질문은 제안값의 명시적 확인을 요구한다.
- `failed`에는 저장할 새 Profile이 없다. `complete`도 FastAPI가 DB 저장을 완료했다는 뜻이 아니다.

## Spring 공개 결과 매핑 제안

| AI 결과 | Spring의 권장 처리 | 공개 결과에 필요한 정보 |
| --- | --- | --- |
| `complete` | Profile 재검증 후 DRAFT와 Attempt를 저장한다. 저장 성공 시에만 200을 보낸다. | 기존 `draft`, `attempt` |
| `needs_confirmation` | Profile·상태·질문을 함께 재검증하고 DRAFT와 확인 메타데이터를 원자적으로 저장한다. CONFIRMED는 건드리지 않는다. | `draft`, `attempt`, `draftReview` 후보 |
| `failed` | 새 DRAFT를 만들지 않는다. Attempt 실패를 기록하고 이전 DRAFT·CONFIRMED를 보존한다. | 안전 오류와 기존 상태 |

`draftReview` 후보는 `draftId`, `draftVersion`, `fieldStates`(10개), `questions`(`field`, `reason`, `questionId`), `errorCode`로 구성한다. GET 프로젝트 상세에서도 동일한 확인 메타데이터를 재조회할 수 있어야 페이지를 다시 열어도 질문이 사라지지 않는다. `draftId`와 `draftVersion`이 바뀌면 오래된 질문은 새 초안에 적용하지 않는다. `needs_confirmation`의 Attempt를 기존 `SUCCEEDED`로 표시할지 새 상태를 추가할지는 Full Stack A가 공개 상태 의미와 함께 결정해야 한다.

## 확인 저장 제안

- 화면은 모든 `suggested` 값을 확인 대상으로 표시하고 `unknown`·`unresolved` 필드의 수정/미정 선택을 허용한다. `needs_confirmation`을 자동 확인하거나 자동 저장하지 않는다.
- 기존 `PATCH /api/projects/{projectId}/profile`은 전체 10개 `data`를 받는다. 확인 필요 초안에서는 클라이언트가 질문 ID별 확인을 명시했다는 정보가 추가로 필요하다. `acknowledgedQuestionIds` 같은 필드를 도입할지, 별도의 확인 동작으로 증명할지 합의해야 한다. 서버는 활성 draft의 질문 집합 및 버전을 대조하고, 일부 누락·오래된 버전·다른 프로젝트의 응답을 저장하지 않아야 한다.
- 사용자가 값을 바꾸면 기존 공개 계약대로 USER 출처와 빈 근거가 된다. 제안값을 유지해 확인하면 DOCUMENT 출처와 검증된 근거를 유지할 수 있다. null은 UNKNOWN이다. 확인 후에도 null 필드는 허용한다.
- 저장 성공 여부는 Spring의 트랜잭션 결과로만 표시한다. 저장 실패·충돌에서는 화면의 편집값과 이전 CONFIRMED를 보존한다.

## 합의가 필요한 항목

1. 공개 `draftReview`의 정확한 이름·형식, 저장 위치·보존 기간, GET 재조회 형태.
2. `needs_confirmation` Attempt 상태와 HTTP 200의 의미. HTTP 200만으로 확인 완료를 뜻하지 않는 규칙.
3. 질문별 사용자 확인 신호와 PATCH 검증 규칙, 확인 화면의 필수 동작.
4. 실패 건 LLM 원본 응답의 7일 보관 주체·전송 경로. 현재 AI HTTP 응답에는 원본이 포함되지 않는다.

이 합의와 Spring·Frontend 구현, 실제 E2E 검증이 완료되기 전에는 복구 모드를 운영에서 활성화하지 않는다.
