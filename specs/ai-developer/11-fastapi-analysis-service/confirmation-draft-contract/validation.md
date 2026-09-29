# 검증 기록

- 실제 ASGI 요청 테스트에서 `suggested`의 `REVIEW_UNAVAILABLE` 질문이 수정 전 502, 수정 후 200 `needs_confirmation`으로 전달됨을 확인했다.
- `suggested`에 `REVIEW_ISSUE`를 붙이거나 `unknown`에 질문을 붙인 응답은 502 `INVALID_ANALYSIS_RESULT`로 거절했다. 기존 `unresolved` 질문 필수 테스트도 통과했다.
- AI 서비스 전체 530개 단위 테스트와 `git diff --check` 통과.
- 기본 Worker는 여전히 기존 Solar 분석만 실행한다. 이 기능은 FastAPI 검증 경계를 준비한 것이며 Spring의 사용자 확인 및 저장 금지 계약, 수정 후 Solar 라이브 평가, 실제 독립 문서 검증은 별도 미완료 작업이다.
