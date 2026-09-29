# 공개 문서 근거 채점 구현 계획

**목표:** 공개 문서 근거 지표의 거짓 오류와 배열 필드의 과대평가를 분리한다.

**구조:** `public_holdout.score_profile`은 정답별로 별칭→출력값→원문 내 값 위치→근거 span을 검사한다. 모호한 매핑은 별도 카운트로 두고 안전 평가 CLI가 결과·요약·점수 버전을 보존한다.

**대상:** `ai_service/agentfit_ai/public_holdout.py`, `public_holdout_evaluation.py`, `ai_service/tests/test_public_holdout.py`, 이 폴더의 `validation.md`.

## 작업 1: 잘못된 근거 판정 재현

- [x] 목록 기호가 gold quote에만 있어도 값 구간을 근거가 덮으면 일치하는 실패 테스트.
- [x] 같은 값의 다른 등장만 인용하면 근거 오류인 회귀 테스트.
- [x] 배열의 여러 값이 하나의 span에 들어가거나 한 값이 두 체크 별칭과 맞으면 판정 불가인 실패 테스트.
- [x] gold quote에 값 문자열이 없으면 판정 불가인 실패 테스트.

## 작업 2: 채점 구현

- [x] 동일 문서 내 유일한 gold quote와 출력값의 정확 등장 구간을 사용해 일치/오류/판정 불가를 계산한다.
- [x] `matched + wrong_evidence + missing_alias + indeterminate == total_checks`를 검증한다.
- [x] 전체 출력에서 원문·Profile을 저장하지 않는 기존 경로를 유지한다.

## 작업 3: 평가 산출물

- [x] 결과와 요약에 `indeterminate_evidence_checks` 및 `public-evidence-v2`를 기록한다.
- [x] 예전 5건을 새 평가기로 한 번 재실행하되 튜닝 결과로 분류하고 이전 실행과 인과 비교하지 않는다.
- [x] 전체 테스트·diff check·feature 브랜치 push·Linux CI를 확인한다.

## 경계 검토

- 후보값과 앵커가 대소문자만 다르면 정확한 원문 구간이라고 보지 않는다.
- span 하나에 두 배열값이 있으면 귀속을 추측하지 않는다.
- 정답 별칭이 겹쳐 한 값이 여러 체크와 맞으면 중복 정답을 만들지 않는다.
- 수정 뒤 과거 평가 파일과 그 해시는 그대로 유지한다.
