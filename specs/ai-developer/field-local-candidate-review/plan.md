# Field-local Candidate Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 사용자가 직접 구현·자율 진행을 승인했다.

**Goal:** 필드별 후보 검토와 누락 검토를 기존 파이프라인에서 선택적으로 실행한다.

**Architecture:** 별도 검토 모듈이 필드별로 엄격한 응답 범위를 제한한다. 서버가 10개 누락 응답을 합쳐 기존 검토 계약으로 반환한다. bool 옵션은 Python 내부 연결만 바꾼다.

**Tech Stack:** Python3.13, unittest, 기존 NVIDIA transport와 Profile 검증기.

**Spec:** [spec.md](spec.md)

## Global Constraints

- 기본 옵션 false, 공개 HTTP/Profile/Spring 계약 변경0. candidate_batch 고정20, 최대240개/100000자/10필드.
- 검토 최대31호출, 전체64공유예산. NVIDIA-only retry0, 오류 후 중단. 로컬 suite별180초, 실제 모델은 로컬/리뷰/CI 후 별도동결93호출/5400초/요청1800초.
- 키/원문/원본응답 로그0. 다른 계획 workspace 삭제0. feature 브랜치 commit/push, 병합/배포0.

## Review Focus

1. 반복 인용이 다른 필드·확정 상태에 있을 때 잘못된 ID로 다른 판단을 덮어쓰지 못해야 한다(T1).
2. 마지막 누락 필드의 오류도 부분 성공을 반환하면 안 된다(T1,T2).
3. falsey callable transport는 실제 기본 네트워크로 바뀌면 안 된다(T1).
4. 후보240개가10필드에 분산돼도 검토31회/공유64회 한도와 실패 위치를 지켜야 한다(T1,T2).
5. bool 옵션이 잘못됐거나 비기본 경로의 제공자가 실패하면 extraction 전 거절 또는 첫 오류 중단이 이뤄져야 한다(T2).

### Task 1: 필드별 검토 모듈

**Files:** Create ai_service/agentfit_ai/candidate_field_review.py, ai_service/tests/test_candidate_field_review.py.

**Interfaces:** `review_candidates_by_field(document, frozen, labels, key, *, transport=None, review_model=MODEL, review_calls=None, review_reasons=None) -> dict` returns 기존 checkedFields/missingFields/wrongCandidateIds. 모델은 기존 NVIDIA 목록만, field 의미는 explicit-v1 고정.

- [x] Step1: 실패 테스트 작성. confirmed ID 정확1회/동일field 배치20/필드별 특수 지침/반복 인용 위치 보존, 빈 후보여도10필드, 외부 ID/순서/사유/최종field 오류/비bool 거절, 잘못된 입력은 전송0, falsey전송, provider 오류후추가0, 최악분배31회, 안전진단을 검증한다.
- [x] Step2: `python -m unittest tests.test_candidate_field_review -v` 실행. Expected: 새 module 없음으로 RED.
- [x] Step3: 공통 _sender/_validate_frozen/_payload/라벨·사유 검증기를 재사용해 구현. 기능 설명은 features 요청에만 첨부하고 전체10field 응답이 완료된 뒤 반환한다.
- [x] Step4: 같은 테스트 실행. Expected: 모두 PASS. 기존 unit suite도180초 한도 실행. 미실행/실패를 기록한다.
- [x] Step5: Task1 commit 및 task-done 같은 테스트로 완료 기록.

### Task 2: 선택형 전체 분석 연결

**Files:** Modify ai_service/agentfit_ai/candidate_analysis_pipeline.py. Create ai_service/tests/test_field_local_candidate_pipeline.py.

**Interfaces:** consumes Task1 검토 함수. `analyze_integrated_candidates(..., field_local_review=False)`와 `analyze_nvidia_candidates(..., field_local_review=False)`가 bool 검증 후 전달. stage COVERAGE_REVIEW_FAILED와 기존 공유 meter/observer/result 유지.

- [x] Step1: 실패 테스트 작성. 실제 파이프라인+가짜 외부 모델에서10field 전부 검토후동일근거 Profile, 마지막coverage실패면부분없음, 공유예산10에서차단, default/false경로불변, badbool호출0, Nvidia wrapper옵션전달·첫503후추가0을 검증한다.
- [x] Step2: `python -m unittest tests.test_field_local_candidate_pipeline -v`. Expected: field_local_review 미지원 RED.
- [x] Step3: bool 옵션·분기·전달 추가. 기존 default reviewer 함수는 수정하지 않는다.
- [x] Step4: 같은 테스트 PASS 및 unit/runtime/contract/core suite별180초 검증. Expected: 기존 gate와 신규검증 모두PASS, Windows skip은별도보고.
- [ ] Step5: commit/task-done→fresh 최종review1회(가장적합한 모델 명시, 하위위임0)→중요문제1pass RED/GREEN→최종commit/push와 exactHEAD CI. 실평가는 최종code freeze를 새로 생성한 뒤 시작한다.

## Self-review

각 명세의 필드/ID/누락/실패/예산/기본 경로 요구를 위 테스트에 대응했다. Task1 출력은 기존 review 계약이므로 Task2 finalizer 변경은 불필요하다. 실제 모델 의미 정확도는 fake transport 테스트의 판단 범위 밖이다.
