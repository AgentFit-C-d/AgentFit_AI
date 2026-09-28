# 구현 계획

1. 복구형 분석의 검토 관측 상태를 호출별로 유지하고, 기본값이 꺼진 `require_issue_free_review` 옵션을 추가한다.
2. 성공 직전 이슈 이력이 있으면 검증된 최종 Profile을 `project_draft`로 `needs_confirmation` 상태로 변환한다. 안전 오류 코드만 추가한다.
3. 가짜 제공자 테스트를 먼저 실패시킨 뒤 구현하고 전체 회귀 테스트를 실행한다.
4. 선택형 합성 평가에서 자동 확정 감소와 확인 부담을 함께 기록한다. 기존 run1/run2는 수정하지 않는다.
5. 결과·한계를 기록하고 변경 파일만 커밋해 `feature/review-issue-confirmation-gate`에 push한다.
