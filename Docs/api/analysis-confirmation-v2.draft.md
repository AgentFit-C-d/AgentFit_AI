# confirmation-v2 Spring·Frontend 인계 초안

상태: AI 내부 v2는 구현되어 있으나 **공개 질문 계약은 팀 합의·구현 전**이다. 기존 v1 초안을 v2로 해석하지 않는다. 공개 OpenAPI를 이 문서가 변경하지 않는다.

## 구현된 AI 응답

`AGENTFIT_ANALYSIS_MODE=integrated-candidates`의 `/internal/v1/analyze`를 `X-AgentFit-Analysis-Contract: confirmation-v2`로 호출한다. 기존 Bearer·문서ID·요청ID·raw 입력 규칙은 유지된다.

| outcome | 키 | 의미 |
| --- | --- | --- |
| needs_confirmation | contract, outcome, requestId, profile, fieldStates, questions, error | 검증된 제안이며 사용자 확인 필요 |
| failed | contract, outcome, requestId, error | 새 초안 없음; 안전 실패 코드 |

v2는 `complete`를 자동 확정 결과로 제공하지 않는다. `profile`은 data/sources/evidence/unknownFields다. 저장 ID·kind·version·updatedAt은 Spring이 만든다. `needs_confirmation.error`는 `REVIEW_CONFIRMATION_REQUIRED`다.

10개 필드마다 상태가 반드시 하나 있고 질문은 다음 규칙을 따른다.

| 상태 | 값 | 질문 |
| --- | --- | --- |
| unknown | null | 없음 |
| suggested | null이 아닌 값([] 포함) | CONFIRM_SUGGESTION 한 개 |
| unresolved | **null 또는 근거가 있는 제안값** | REVIEW_ISSUE 또는 CANDIDATE_MISSING 한 개 |

각 질문은 정확히 `{ "field": "frontend", "reason": "REVIEW_ISSUE", "questionId": "confirm_frontend" }` 형태다. 임의 질문 텍스트·원문·토큰은 없다. field 중복·questionId 변조·질문 누락·상태와 모순되는 사유·알 수 없는 필드를 거절해야 한다. `unresolved`의 알려진 값을 null로 강제 삭제하면 v2 제안 복구의 의미가 달라진다.

## Spring 저장과 화면 연결 결정안

1. 응답 requestId, Profile·문서 근거, 상태·질문을 재검증한다. 저장 성공 전에는 공개200을 보내지 않는다.
2. 초안과 리뷰 메타데이터를 같은 draftId/draftVersion에 원자적으로 연결한다. 기존 CONFIRMED를 덮어쓰지 않는다.
3. 공개 분석/상세 응답에서 같은 리뷰를 재조회할 형식이 필요하다. `draftReview`는 **미합의 후보 이름**이다. 현재 mock은 리뷰를 내부 보관하지만 기존 공개 DTO에 내보내지 않는다.
4. 사용자가 suggested/unresolved의 제안 유지·수정·미정을 명시적으로 확인하게 한다. 현재 전체 data PATCH만으로 질문별 확인을 증명할 수 없다. `acknowledgedQuestionIds` 또는 동등한 확인 계약을 합의하고 초안 버전/질문 집합을 서버에서 검사해야 한다.
5. 새 분석이 만든 초안에는 이전 초안의 질문 확인을 재사용하지 않는다. 충돌 시 편집값을 보존하고 다시 검토한다.
6. null 저장은 허용한다. 값 유지/변경에 대한 DOCUMENT·USER·UNKNOWN 출처 계산은 현재 공개 규칙을 따른다.

mock에서는 검증된 초안 저장을 Attempt.SUCCEEDED로 표현한다. 사용자 확인 완료를 뜻하지 않는다. 공개 화면 상태 의미와 문구는 Spring·Frontend가 합의해야 한다.

실패 건 원본 진단 전송은 현재 AI HTTP 응답에 없다. 7일 보관 정책만으로 실제 전달/권한/삭제 구현이 생기지 않는다. [mock 인계서의 실제 연결 체크리스트](core-analysis-mock-handoff.md)를 완료하기 전에는 실제 Spring 통합 완료로 표시하지 않는다.
