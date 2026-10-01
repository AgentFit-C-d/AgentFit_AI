# DB 이름 별칭 수정 구현 계획

> 실행: superpowers:executing-plans를 사용해 현재 세션에서 직접 구현한다.

**Goal:** DB 별칭 때문에 정상 값이 scalar 충돌로 사라지는 후처리 오류를 수정한다.
**Architecture:** DB 이름만 보수적으로 식별하는 순수 함수와 기존 Profile 변환의 작은 분기.
대표 값은 원문 그대로이며 기존 근거·확인·저장 계약을 유지한다.
**Tech Stack:** Python, unittest, 기존 candidate/confirmation 검증기. 추가 의존성 없음.
**Spec:** [spec.md](spec.md)

## 제약·검토 초점

- 새 모델 호출·재시도 예산 0. 로컬 회귀/전체 단위 테스트만 실행한다.
- 기존 결과와 무관한 dirty 파일 보존. 큰 goal paused 유지.
- 숫자 버전의 정밀도·미지정 차이, 호환 제품, 부정/계획 문구를 병합하지 않는다.
- 후보 순서와 무관하게 원문 첫 표기 선택. 대표에 맞는 근거만 Profile에 연결한다.
- 기존 확인 필요와 모든 modelDecisions를 유지한다.

## Task 1 — 별칭 동등성 판정과 재현 회귀

**파일:** `ai_service/agentfit_ai/database_names.py`, `candidate_first_profile.py`,
`ai_service/tests/test_database_name_aliases.py`, `ai_service/tests/fixtures/database_name_aliases.json`,
`work/harness/database-name-aliases/`.

**인터페이스:** `database_identity(value: str) -> tuple[str, str | None]`는 허용 이름을
`('postgresql', version)`으로, 나머지를 `('literal', value)`로 구분한다.
Profile 함수 시그니처·공개 응답 변경 없음.
추가 보호: `complete_database_mention(document: str, span: dict) -> bool`은 모든
occurrence의 인접 버전·불완전 토큰·알려진 수식 이름을 검사해 병합을 보류한다.

- [x] 저장 응답 해시와 전체 reviewed stage를 동결하고 최소 회귀 fixture를 추출한다.
- [x] 실제 저장 응답 및 변형의 독립적인 기대값을 작성한다. 수정 전 실패를 확인한다.
- [x] 이름의 전체 일치와 정확한 버전 비교를 구현하고 database scalar 변환에만 연결한다.
- [x] 원문 근거, 다른 DB/버전, 다른 필드, tentative/negated 및 확인 계약 회귀를 검증한다.
- [x] 동일 고정 평가 세트를 전후 재생하고 전체 단위 테스트를 실행한다.
- [x] 최종 diff와 별도 리뷰를 완료하고 관련 파일의 commit/push 범위를 확정한다.

커밋·원격 반영 및 종료 상태는 `work/harness/database-name-aliases/STATE.md`에 기록한다.

검증 명령: `python -m unittest discover -s tests -p test_database_name_aliases.py -v`,
`python -m unittest discover -s tests -q` (각 `ai_service`에서 기존 Python 환경 사용).
로컬 검증 15분 상한, 예상치 못한 실패는 원인 확인 후 최대 1회 수정·재실행.
운영·실제 모델 의미 정확도는 이번 로컬 재생 결과로 주장하지 않는다.
