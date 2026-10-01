# Classification Stage Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. 사용자 자율 승인에 따라 직접 구현한다.

**Goal:** 전체 문서 분류에서 모델과 후보 묶음 크기를 독립 선택한다.

**Architecture:** 기존 classifier의 묶음 설정을 검증하고 pipeline에서 분류에만 NVIDIA 모델·키·meter를 선택한다. 기존 검증/실패/최종화 계약은 재사용한다.

**Tech Stack:** Python3.13, unittest, 기존 Solar/NVIDIA adapter.

**Spec:** [spec.md](spec.md)

## Global Constraints

- 기본 모델 상속·묶음30 유지. 공개 HTTP/Profile/Spring 변경0. 후보 최대240·문서100000자·대표기능30 이하 유지.
- 전체64회 공유예산·분류 호출600초·NVIDIA-only retry0 유지. 로컬 suite별180초, 이 구현 단계 실제API0. 실제 비교는 코드/자료/모델을 새 freeze로 고정하고 별도 호출·시간 예산 등록 후 실행한다.
- 비밀·원문·원본 응답 로그0. 이전 결과/gold/freeze/scratch 삭제·덮어쓰기0. feature 브랜치 commit/push, 병합·배포0. 무료 확인된 모델/엔드포인트만 실호출한다.

## Review Focus

1. 31개·240개 후보의 마지막 묶음과 반복 원문의 서로 다른 위치가 빠지거나 중복되지 않는가(T1).
2. 마지막 묶음에서 누락/중복/외부 ID/제공자 실패가 나면 부분 라벨·검토·최종화가 진행되지 않는가(T1,T2).
3. 잘못된 모델과 bool/float/문자열 묶음 값이 빈 후보와 통합 진입점에서도 외부 작업 전에 거절되는가(T1,T2).
4. 혼합/NVIDIA-only에서 분류만 NVIDIA로 선택했을 때 올바른 키·전송을 사용하고 추출/검토 설정과 falsey 명시 전송을 보존하는가(T2).
5. 15묶음의 추가 호출도 공유 예산에 포함되고 NVIDIA 실패에 재시도/다른 모델 대체/비밀 출력이 없는가(T2).

### Task 1: 분류 묶음 설정

**Files:** Modify ai_service/agentfit_ai/candidate_first_profile.py. Create ai_service/tests/test_candidate_classification_batches.py.

**Interfaces:** Produces `classify_profile_candidates(document, frozen, key, *, transport=None, field_semantics='legacy', nvidia_model=None, batch_size=30) -> list[dict]`. Existing labels contract unchanged; ValueError for invalid batch.

- [x] Step1: 기본30과 선택15의 전체 ID/원문/반복 위치/불변 입력, 31·240 경계, 빈 입력 bad config, 마지막 batch 누락/중복/외부 ID/제공자 오류 테스트 작성.
- [x] Step2: `python -m unittest discover -s ai_service/tests -p test_candidate_classification_batches.py -v` (PYTHONPATH=ai_service). Expected: batch_size 미지원 RED.
- [x] Step3: 엄격한15/30 검증과 기존 반복문의 묶음 크기만 변경.
- [x] Step4: 같은 명령 Expected: PASS. API0.
- [x] Step5: task commit 후 task-done 같은 검증으로 완료 기록.

### Task 2: 분류 전용 모델 경로

**Files:** Modify ai_service/agentfit_ai/candidate_analysis_pipeline.py. Create ai_service/tests/test_classification_stage_routing.py.

**Interfaces:** Consumes T1 batch_size; produces `analyze_integrated_candidates(..., classification_model=None, classification_batch_size=30)` and `analyze_nvidia_candidates(..., classification_model=None, classification_batch_size=30)`. None inherits candidate route; explicit NVIDIA uses nvidia_key/nvidia_send. Result and failure contracts unchanged.

- [x] Step1: 실제 파이프라인+가짜 외부 전송으로 혼합/NVIDIA-only 분류 모델 분리·15묶음·기본 경로·동일 Profile/근거, bad config 호출0, falsey 전송, 마지막 분류 실패·공유 예산 차단·안전진단 테스트 작성.
- [x] Step2: `python -m unittest discover -s ai_service/tests -p test_classification_stage_routing.py -v` (PYTHONPATH=ai_service). Expected: 새 옵션 미지원 RED.
- [x] Step3: 검증·분류 경로 선택·wrapper 전달만 구현.
- [x] Step4: 같은 명령 PASS; unit/runtime/contract/core 전체 suite별180초. Expected: 기존 gate와 신규 검사 PASS, Windows skip 별도 기록.
- [ ] Step5: task commit/task-done→fresh 최종 reviewer1회→중요 문제만 RED/GREEN 수정→최종 commit/push→exactHEAD Linux CI 확인.

## Self-review

T1의 strict batch와 labels 반환은 T2가 그대로 소비한다. 요구1·2는T1, 요구3·4는T2, 요구5는공통 제약과 최종 diff/review로 확인한다. 모델 정확도를 가짜 전송 테스트로 주장하지 않는다. 새 실제 평가는 이 구현의 gate 이후 새 프로토콜로 진행한다.
