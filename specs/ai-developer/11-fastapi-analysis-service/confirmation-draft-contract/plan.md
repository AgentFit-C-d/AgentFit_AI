# 구현 계획

1. FastAPI 실제 요청으로 제안 질문 허용과 잘못된 제안·unknown 질문 거절을 재현하는 테스트를 작성한다.
2. `_checked_confirmation`의 질문 필드·사유 검증을 최소 변경한다. `unresolved` 전부 질문 필수 조건은 유지한다.
3. 관련 테스트와 전체 AI 서비스 테스트를 실행하고 출력에서 원문·임의 사유 노출이 없는지 확인한다.
4. 결과·남은 Spring 확인/저장 계약을 기록하고 `feature/confirmation-draft-contract`에 push한다.
