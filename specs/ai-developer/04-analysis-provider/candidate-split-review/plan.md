# 후보 분리 검토 구현 계획

> 실행: executing-plans와 test-driven-development 절차로 직접 구현한다.

**Goal:** 복합 검토 요청을 후보 판단과 원문 누락 검사로 분리하고 실제 H02에서 검증한다.
**Architecture:** 기존 후보 파이프라인 내 선택형 분기. 신규 검토 모듈은 기존 형태의 검토 결과를 반환한다.
**Tech Stack:** Python, unittest, 기존 Solar transport.
**Spec:** [spec.md](spec.md)

## 제약 및 검토 초점

기본 서비스·Profile·기존 보류 조건 유지. 20개 묶음, medium/8192/600초 유지. 원문·정답·비밀 공개 금지.
반복 표현의 위치 보존, 잘못된 후보 제거 후 누락 검토, 마지막 묶음 누락, 빈 후보, 미완료·중복·타 묶음 ID가 자동 완료로 이어지지 않는지 확인한다.

## 작업

- [x] 1. `tests/test_candidate_split_review.py`에 21개 확정 후보와 미확정 후보의 분리, 중복 값, 잘못된 ID·중복 ID·checked 누락·미완료·모델 불일치·빈 후보 테스트를 작성한다. `unittest discover -s tests -p test_candidate_split_review.py -v`에서 미구현 실패를 확인한다.
- [x] 2. `agentfit_ai/candidate_split_review.py`의 `review_candidates_separately(document, frozen, labels, key, *, transport)`를 구현한다. 기존 validator와 source mention을 재사용하고 후보 검토 20개 묶음 뒤 누락 검사를 수행한다. 위 테스트를 통과시킨다.
- [x] 3. `analyze_candidate_first(..., split_review=False)` 및 평가 CLI `--split-review`를 연결한다. 기본 경로와 선택 경로, 실패 시 projected 이벤트 부재·오류 후보 제외·확인 필요 처리를 회귀 검증한다. 결과에 review_mode를 기록한다.
- [x] 4. 전체 `python -m unittest discover -s tests -q`, diff 검사, 코드 리뷰, commit/push, CI. 승인된 manifest 해시로 H02를 source-occurrences/stage-diagnostics/split-review와 함께 1회 실행한다. 검증 기록에 결과·한계·다음 행동을 남긴다. 결과는 검토 미완료 실패이며 품질 개선 미입증이다.

## 상태 기록

- 시작점 230872c, feature/candidate-split-review. 직전 목표 턴은 현황 설명으로 코드 진전 없음. 실제 체크아웃과 마지막 실패 기록을 재확인했고 새 실험 명세·계획을 작성했다.
- 사용자 소유 work/harness/service-readiness는 보존한다. 이 문서와 validation.md가 본 작업 상태 기록이다.
