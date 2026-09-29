# 동일 후보 검토 비교 구현 계획

> executing-plans로 직접 구현한다. TDD 후 독립 최종 리뷰를 받는다.

**Goal:** 동일한 후보·분류를 공유해 검토 모델의 차이를 측정하고 실제 불일치를 원문 위치까지 추적한다.
**Architecture:** 기존 후보 분석의 최종 변환 함수를 공유하고 분리 검토에 제공자 선택을 추가한다. 평가 CLI만 여러 검토를 순서대로 호출한다.
**Tech Stack:** Python unittest, 기존 Solar/NVIDIA HTTP adapter, 기존 승인 문서 전처리.
**Spec:** [spec.md](spec.md).

## 제약과 검토 초점

- 기본 서비스·Profile 유지, 전체 원문/응답/키 저장 금지. 실패를 성공으로 바꾸지 않는다.
- NVIDIA 키가 Solar로 전달되거나 반대인 경우, 응답 모델 위장, 모델 사이 mutable 상태 공유, 실패한 모델 분모 제외, 진단에 값 노출을 중점 검토한다.
- 시작점7b1b3a3. 사용자 소유 work/harness/service-readiness는 변경하지 않는다. 직전 평가 세션51531은 종료됐고4/6 확인 상태다.

## 작업

- [x] 1. `tests/test_candidate_paired_review.py`에 NVIDIA 경로·반환 모델 거절·length 분할 부재 및 최종 변환 동등성의 실패 테스트를 먼저 쓴다. `candidate_split_review.py`의 `review_model` 선택과 `candidate_first_profile.py`의 `finalize_candidate_analysis` 분리를 구현한다. 관련 기존 테스트도 통과해야 한다.
- [x] 2. `candidate_paired_review.py`에 `evaluate_paired(case, solar_key, nvidia_key, models, *, extractor=None, classifier=None, reviewer=None, on_update=None)`와 CLI를 구현한다. 준비된 단일 문서에서 추출·분류1회, deep copy로 모델별 검토/최종 변환을 실행한다. 모델 실패와 공통 실패, 키 사전 차단, 안전한 ID·집계만 출력하는 계약을 RED→GREEN으로 검증한다. CLI는 manifest의 기존 hash·전처리·case-id를 재사용하고 repeatable `--review-model`을 지원한다. 기본 비교 순서는 solar-pro4,deepseek-ai/deepseek-v4.1-flash.
- [x] 3. 관련 및 전체 테스트·diff 검사·독립 리뷰·commit/push·Linux CI를 확인한다. 승인된 H02 실제 비교를 실행해 프로세스/부분 결과를 추적하고, source 위치를 로컬에서 대조해 backend 판정과 이름 투영의 원인을 기록한다. 평가 개선과 배포 가능 여부를 분리한다.

## 실행 기록

- 설계 자체 검토: 기존 호출·검증 의미 유지, 공유 원문은 복사/읽기 전용 취급, API에 정답 진단 미전달. NVIDIA 모델별 추론 설정 차이가 있어 순수 모델 가중치만의 효과라고 부르지 않는다.
- 명세·계획 작성 후 사용자의 목표 단위 자율 승인을 적용해 직접 진행한다.
- 작업1: 누락 인자/함수의 RED6건을 확인하고 기존 회귀와 함께21건 GREEN.
- 작업2: 누락 비교기 RED5건, 설정 진단 누락 RED1건을 확인한 뒤 CLI 포함 새12건 및 기존 관련15건(총27건) GREEN. `on_update`는 공통 입력 준비와 모델별 종료 시 안전한 부분 집계를 deep copy로 전달한다. 부분 파일의 `state=running`은 종료가 아니며 `finished`만 최종 집계다.
- 작업3 완료: 전체848건(6건 건너뜀)·독립 리뷰·코드5c82f5c push·Linux CI36625914141 성공 확인. --env-file의 argparse 필수 지정은 경미한 정리로 보류했다. 승인된 H02의 비교 종료와 두 모델 결과를 확인했다. Solar4/6·DeepSeek5/6이지만 DeepSeek의 더 많은 제외와 backend 골드의 범위 불명확성이 남아 모델 승격은 하지 않는다. 상세 근거는 validation.md를 따른다. 이 평가 기능 완료는 실사용 목표 완료가 아니다.
