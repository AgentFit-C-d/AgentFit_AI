# 묶음 검토 8K 실험 계획

**목표:** 기존 검토 계약을 유지하며 평가 전용 출력 상한만 8,192토큰으로 조정한다.

1. 실패 테스트: `group_review_payload`의 기본 4,096과 명시적 8,192, 잘못된 상한 거부; 분석기의 grouped_review 옵션이 실제 전송에 전달되는지 확인한다.
2. 최소 구현: 새 `group_review_max_tokens`는 묶음 검토에서만 적용하고, 나머지 전송 경로는 유지한다.
3. 실패 테스트: CLI `--group-review-8k`는 source selector·grouped·accuracy-first·extended 조건에서만 허용되고 plan과 analyzer에 8,192를 기록한다.
4. CLI 연결 후 관련 테스트와 전체 테스트를 실행한다.
5. 이미 튜닝한 Campfire 1건을 실제 실행해 세 묶음 완주·오확정·토큰을 기록한다. 첫 문서가 유효할 때만 튜닝 5건으로 확대한다.
6. 결과와 한계를 validation에 기록하고 `feature/grouped-review-8k`로 push해 Linux CI를 확인한다. 기본값으로 승격하지 않는다.
