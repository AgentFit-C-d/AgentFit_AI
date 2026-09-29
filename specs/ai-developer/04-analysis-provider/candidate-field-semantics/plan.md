# 후보 필드 의미 통일 구현 계획

> executing-plans로 직접 구현한다. 각 단계 TDD, 마지막 독립 코드 리뷰를 수행한다.

**Goal:** 분류와 검토의 필드 정의를 통일한 선택형 실험을 같은 후보로 검증한다.
**Architecture:** 공통 의미 지침과 legacy/explicit-v1 선택을 후보 분석 경계에 연결한다. 평가 전용 재생 함수는 기존 JSON의 위치·라벨을 검증하고 추출 없이 두 정책을 비교한다.
**Tech Stack:** Python 표준 라이브러리·unittest·기존 제공자 adapter.
**Spec:** [spec.md](spec.md).

## 제약과 검토 초점

- 공개 API·Profile·기본 서비스·legacy 요청 유지. 문서·정답·키·원본 응답 저장 금지.
- 확인 필요를 완료로 승격하지 않는다. snapshot 반려 수는 보존한다.
- 원문 해시/위치/ID 변조, 모델별 키 혼용, 평가 정책 사이 mutable 상태 공유, 실패 분모 누락, 정책 선택을 기록하지 않는 비교를 검토한다.
- 시작8780711. 기존 source-name-expressions worktree는 clean이고 실행 중 프로세스가 없어 재사용한다. 새 브랜치는 feature/candidate-field-semantics. 사용자 소유 service-readiness 폴더는 수정하지 않는다.

## 작업

- [x] 1. `candidate_field_semantics.py`의 `field_semantics_instructions(policy)`와 정책 상수를 만든다. legacy는 빈 문자열, explicit-v1은 공통10필드·역할·확정 범위 지침, 미지원 값은 ValueError다. `candidate_first_profile`의 payload/classify/coverage/analyze 및 `candidate_split_review`에 `field_semantics='legacy'`를 전달한다. 새 tests/test_candidate_field_semantics.py로 기본 요청 불변과 모든 의미 판단 경계의 동일 지침 및 조기 거절을 RED→GREEN 검증한다.
- [x] 2. `candidate_review_replay.py`의 `restore_snapshot(case, snapshot)`과 `evaluate_review_policies(case, snapshot, key, model, *, policies=('legacy','explicit-v1'), reviewer=None, on_update=None)`를 구현한다. 재생 검증과 오류/반려/변이/진행 출력/안전 진단 테스트를 먼저 작성한다. 결과는 모델·정책별 ID/수치·검사 집계만 포함하며 기존 field summaries/최종 변환을 재사용한다. 실행 명령은 승인 manifest 사전검증을 하는 로컬 driver로 고정하고 결과에 입력 snapshot hash·정책을 기록한다.
- [x] 3. 관련·전체 검사·독립 리뷰·commit/push·Linux CI 후 승인 H02에서 DeepSeek의 두 정책을 실제 비교한다. 프로세스 핸들·출력 state를 추적하고 원문과 안전 ID를 로컬 대조한다. 정상 정보 유지와 거짓 확정을 함께 기록하고 다음 행동을 결정한다.

## 설계 판단

- 사용자 승인에 따라 추가 확인 없이 진행한다. 기존 필드 의미를 새 공개 모델로 바꾸지 않고 실험 단계에서 정확히 전달한다.
- 분류까지 새 지침을 적용한 전체 실행과 검토만 바꾼 재생은 별개다. 이번 실측은 검토 효과만 확인하며 분류 개선이라고 보고하지 않는다.
- 테스트에서 프롬프트 전달을 검증해도 의미 정확도를 증명하지 않는다. 실제 원문 대조는 작업3에서 수행한다.

## 실행 기록

- 작업1: 새 인자/모듈 부재 RED5건 후 공통 지침 연결, 관련38건 GREEN. legacy 요청을 두 경로에서 대조했고 새 지침은 분류·전체 검토·분리 후보/커버리지 검토에 전달된다.
- 작업2: 재생 모듈 부재 RED6건 후 입력 검증·상태 분리·안전 집계 구현. 새11건 및 기존24건 총35건 GREEN. 재생은 분류 라벨을 수정하지 않는다.
- 명세 자체 검토: 이번 실험의 확정 범위는 문서의 현재 목표 범위다. 실제 확정 요구가 미구현이라는 이유로 제외하지 않으며 명시적 이후 확장 범위를 현재 요구로 승격하지 않는다. 모호한 도입 모듈/제공자는 실제 원문 대조에서 따로 기록한다.
- 전체 테스트·독립 리뷰·실제 두 정책 비교·push·CI를 완료했다. 실사용 전체 목표는 미완료이며 active다.
- 전체868건(6건 건너뜀) 통과. 독립 리뷰는 Critical/Important 없음, Minor1건: 재생기의 반려 상한240과 생성기의 무제한 반려 수가 다르다. 이 실험은 최대240개 반려 snapshot만 지원함을 기록하고 더 큰 입력 지원은 보류한다. 실제 H02는4개다.
- 리뷰 판단 보류 처리: 실제 H02 의미 품질과 driver 저장 안전성은 메인에서 검증한다. driver는 승인 manifest/원본/추출 hash를 검사하고 write_safe_json에 키·원문·원본 경로를 금지 문자열로 전달한다. 짧은 fixture 키와 고정 ID의 일치는 실제 제공자 키 형식의 유출로 보지 않으며 실제 키를 출력하지 않는다.
- 코드acb411b push, Linux CI36632263553 success 확인. 실제 세션66181 종료 코드0, 두 정책 모두5호출 완료. 발생 위치8개 관찰은3→5개 일치, 기존6개 검사는 모두 통과했다. 웹 형태2개가 복구됐으나 최종 기능 목록은 같았다.
- Ruling: 남은3개 발생 위치 제외를 기능 전체 누락이라고 부르지 않는다. 같은 기능의 C053이 보존됨을 원문/위치로 확인했다. 잘못 해석하면 반복 인용을 늘리는 튜닝으로 흐를 수 있어 사전 결과는 유지하고 의미와 위치 지표를 분리했다.
- 다음 행동: 원문에서 동작과 대상이 드러나는 기능 후보를 확보하고 최종 대표 기능의 의미 커버리지를 평가한다. 특정 별칭3개를 복구하는 추가 프롬프트 반복은 하지 않는다. 상세 근거와 제한은 validation.md에 기록했다.
