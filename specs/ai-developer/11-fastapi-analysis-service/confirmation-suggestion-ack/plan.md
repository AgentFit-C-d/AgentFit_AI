# 구현 계획

1. `project_draft`에 의미 검토 후 제안 질문을 생성하는 선택 인자를 추가한다. 복구형 Solar만 활성화하고 새 사유를 안전 목록에 넣는다.
2. FastAPI 복구 모드 검증에서 모든 `suggested`·`unresolved` 필드의 질문 존재와 사유-상태 일치를 검사한다. 기본 모드는 기존 호환성을 유지한다.
3. 분석기·ASGI 실패 테스트를 먼저 작성해 누락 질문 및 잘못된 사유를 재현한다. 기존 `needs_confirmation`의 Profile과 오류 코드는 유지한다.
4. `Docs/api/analysis-confirmation-v1.draft.md`에 질문 ID가 모든 확인 대상 필드를 덮는 내부 계약을 기록한다. 공개 DTO·저장 API가 아직 합의 전임을 유지한다.
5. 전체 테스트, 실제 합성 문서 로컬 HTTP, diff check, feature 브랜치 push·Linux CI를 확인한다.
