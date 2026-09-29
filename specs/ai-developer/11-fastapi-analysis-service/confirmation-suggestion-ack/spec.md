# 확인 필요 제안의 명시적 질문 계약

## 관찰

실제 로컬 FastAPI→Worker→Solar 합성 문서 실행은 HTTP 200 `needs_confirmation`, 제안 7개·미해결 1개·질문 8개를 반환했다. 다른 경로에서는 의미 검토가 완료된 후 한 필드만 미해결이 되어도 나머지 `suggested` 값에 질문 ID가 없을 수 있다. 기존 인계안은 모든 `suggested`를 사용자 확인 대상으로 정의하지만, 질문 ID만 승인하는 Spring 구현은 이런 값을 확인 없이 저장할 위험이 있다.

## 계약

- `recoverable-solar`의 `needs_confirmation`에서 모든 `suggested`와 `unresolved` 필드에는 각각 정확히 하나의 `confirm_<field>` 질문이 있어야 한다. `unknown`에는 질문을 붙이지 않는다.
- 의미 검토를 완료한 제안의 질문 사유는 새 안전 코드 `CONFIRM_SUGGESTION`, 검토를 끝내지 못한 제안은 기존 `REVIEW_UNAVAILABLE`이다. 미해결 사유는 기존 안전 코드만 허용한다. 질문은 확인 요청이며 자동 승인·저장 신호가 아니다.
- FastAPI는 복구 모드의 누락·중복·상태와 맞지 않는 질문을 `502 INVALID_ANALYSIS_RESULT`로 거절한다. 기본 분석 모드와 공개 Profile·기존 내부 요청 헤더 형식은 유지한다.
- Spring 공개 DTO와 확인 PATCH는 여전히 합의 전이다. AI 내부 응답만으로 DB 저장 완료나 사용자 확인 완료를 선언하지 않는다.

## 검증

1. 의미 검토 후 일부 필드 오류가 나면 남은 모든 제안에 `CONFIRM_SUGGESTION` 질문이 생긴다. 검토 전 실패는 `REVIEW_UNAVAILABLE`을 유지한다.
2. 복구 모드 ASGI 요청에서 제안 질문 누락·잘못된 사유는 502, 올바른 질문은 200 `needs_confirmation`이다. 기본 모드 회귀 테스트도 통과한다.
3. 실제 합성 문서의 로컬 Provider 경로와 전체 테스트·Linux CI를 확인한다. Spring/Frontend 저장 E2E는 별도 미완료로 기록한다.
