# 기능 동작 후보 구현 계획

> executing-plans로 직접 구현하고 마지막 독립 리뷰를 수행한다.

**Goal:** 원문 근거가 확인되는 동작 후보를 기존 의미 검토에 공급한다.
**Architecture:** `operation_candidates.py`에 추출/분류/병합을 분리한다. 기존 NVIDIA adapter·anchor grounding·분류 payload·label validation을 재사용한다.
**Tech Stack:** Python unittest·기존 HTTP adapter.
**Spec:** [spec.md](spec.md).

## 제약·검토 초점

기본 서비스와 legacy 요청 불변. 키·원문·응답 저장 금지. 추출/분류에서 확정 판정 합치지 않음. 같은 위치 라벨 충돌·새ID 재부여·모델 위장·실패 반려 누락·200/60/240 제한을 검토한다. 별도 worktree 없이 clean 5d1a3b1을 feature/operation-candidates로 분기했다.

## 작업

- [x] 1. tests/test_operation_candidates.py에 먼저 RED를 만든다. `extract_operation_candidates(document,key,*,model=MODEL,transport=None)`는 검증된 frozen dict를 반환한다. `classify_operation_candidates(document,frozen,key,*,model=MODEL,transport=None)`는 explicit-v1으로 분류한다. `merge_candidate_sets(document,*sets)`는 `(frozen,labels)` 쌍들을 병합해 새 쌍을 반환한다. 위 상한·위치·반려/충돌·키·정확한 모델을 테스트한다.
- [x] 2. 관련/전체 검증·독립 리뷰·commit/push·Linux CI를 확인한다. 승인된 H02 snapshot과 새 후보를 합쳐 분리 검토/최종 변환까지 실측한다. 저장된 숫자와 원문 위치를 대조하고 다음 행동을 기록한다.

## 상태

구현·테스트·독립 리뷰·push·CI·H02 실제 실험을 완료했다. 실험은 종료 코드0이며 품질 게이트는 미충족이다. 기본 서비스 승격은 보류한다. 사용자 소유 work/harness/service-readiness는 수정하지 않는다.

## 실행 기록

- 작업1의 새7건은 모듈 부재 RED 후 GREEN. 병합된 반려 항목 식별자 충돌을 추가1건으로 RED 재현하고 순차 재할당으로 수정했다. 새8건·관련11건 총19건 통과했다.
- 추출1회와 분류30개씩을 구현했고 기존 adapter/원문 anchor 검증을 재사용한다. 전체 테스트·독립 리뷰·실측은 진행 중이다.
- 독립 리뷰 P2 1건: other 상태 정규화가 누락/잘못된 status를 숨기는 문제를 재현했다. 회귀 테스트의5개 하위 사례 RED 후 원본 행의 필수 키·타입·enum을 먼저 검사하도록 수정해 GREEN. 새9건·관련11건 총20건 통과했다. 한 차례 수정 패스로 처리하고 별도 재리뷰를 반복하지 않는다.
- 리뷰가 판단을 보류한 실제 의미 품질·snapshot 해시는 메인에서 실측한다. preflight의 hash는 확인했고 실측은 아직 전이다. HTTP/Spring 연동·기본 서비스 예산은 이번 실험으로 검증됐다고 주장하지 않는다.

- 최종 코드 dcee55d, 전체877건 중871통과·6건 건너뜀. CI36634503881 success를 재확인했다. H02 실제 실험은 새 후보58개·원문 근거 모호2개 반려·병합183개,10호출·230436ms로 종료됐다. 최종 기능 고유 표현4→15, 지정6개 검사6/6→5/6(C05 외부 연동 누락), needs_confirmation이다. 검토가 명시적 인증 API까지 배제하고 기대효과 표현을 일부 유지해 의미 품질은 미해결이다. 상세 대조는 validation.md에 기록했다.
