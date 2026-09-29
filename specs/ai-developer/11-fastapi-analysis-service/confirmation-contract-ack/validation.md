# 검증 기록

- 복구 서비스 모드의 계약 헤더 누락·다른 값·중복을 실제 ASGI 요청으로 재현했다. 수정 전에는 분석기를 호출하고 500을 반환했으며, 수정 후에는 분석 전 `428 CONFIRMATION_CONTRACT_REQUIRED`를 반환했다.
- 정확한 헤더를 보낸 복구 모드는 기존 확인 필요 초안과 실제 자식 프로세스 경로를 통과했다. 기본 모드의 헤더 없는 요청도 기존 테스트에 포함된다.
- Spring 공개 DTO에는 `fieldStates`·`questions`의 저장/재조회 계약이 없음을 [인계안](../../../../Docs/api/analysis-confirmation-v1.draft.md)에 기록했다. 이 인계안은 합의 전 초안이며 Spring·Frontend 구현을 검증한 결과가 아니다.
- 전체 AI 서비스 단위 테스트 539건과 `git diff --check` 통과.
