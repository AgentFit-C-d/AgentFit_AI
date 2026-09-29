# 제한적 후보 분할 검토 계획

> executing-plans, TDD로 직접 진행. 명세: [spec.md](spec.md).

**Goal:** length로 잘린 후보 검토를 동일 입력의 작은 검토로 복구한다.
**Architecture:** 분리 검토 함수 내부의 1단계 제한적 분할. 원문 누락 검토·기본 경로 유지.
**Tech Stack:** Python unittest, 기존 Solar transport.

## 검토 초점

다른 오류의 무단 재시도, 부분 ID 완료 인정, 실패한 하위 묶음 뒤 진행, 진단에서 부모 실패 은폐, 플래그 조합 오류를 막는다.

- [x] 1. `tests/test_candidate_adaptive_review.py`에 length만 분할·정확한 ID 커버리지·하위 실패 중단·잘못된 계약/timeout/모델/5개 이하/기본 경로 재시도 부재를 RED로 검증한다. CLI adaptive 옵션 연결도 RED.
- [x] 2. `candidate_split_review.py`의 `review_candidates_separately(..., adaptive_review=False)`와 `candidate_first_profile.py`의 같은 옵션, 평가 CLI를 구현한다. 작은 하위 묶음은 최대4개이고 재귀 분할은 없다. 관련 테스트 GREEN.
- [ ] 3. 전체 테스트, diff 검사·독립 리뷰·commit/push·CI. 승인된 H02 진단 평가와 실제 프로세스를 추적하며 validation.md에 결과·판단을 기록한다.

## 상태

시작점 a447085. 직전 진단 평가 PID30404/자식9920 및 셸 세션34082는 종료됐다. 결과 JSON은 failed=1이며 candidate_batch2의 length 종료가 직접 원인이다. 이번 작업에서 사용자 소유 work/harness/service-readiness는 변경하지 않는다.
