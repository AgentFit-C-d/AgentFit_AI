# 원문 프로젝트명 표현 보존 구현 계획

> executing-plans로 직접 구현하며 TDD 후 독립 최종 리뷰를 수행한다.

**Goal:** 확정된 이름 후보들의 원문 표기를 유지하는 확인용 초안을 만든다.
**Architecture:** 순수 원문 구간 결합 함수를 후보 Profile 변환에 연결한다. 모델 호출과 공개 Profile은 유지한다.
**Tech Stack:** Python 표준 라이브러리·unittest.
**Spec:** [spec.md](spec.md).

## 제약·검토 초점

- 문자열 합성·특정 프로젝트명 규칙·확인 상태 자동 승격 금지.
- 다른 위치의 예시에서 괄호 관계를 가져오지 않아야 한다.
- 세 번째 이름·비확정 후보·다른 scalar 필드가 조용히 합쳐지지 않아야 한다.
- Unicode offset과 200 code point 제한을 지킨다.
- 실행 중인 비교 worktree는 수정하지 않는다. 현재 별도 worktree는 b63cac9에서 시작했고 관련 기준 테스트24개가 통과했다. 앱 worktree 도구가 Git 소유권 오류로 실패해 검증된 ignored 경로에 명시적 safe.directory로 생성했다.

## 작업

- [x] 1. `tests/test_source_name_expressions.py`에 원문 괄호 표현이 null로 사라지는 회귀를 먼저 RED로 확인한다. 위 경계 사례와 자동 완료 부재를 함께 검증한다. `source_name_expressions.py`에 `source_name_expression(document, entries)`를 구현하고 `candidate_first_profile.project_candidate_profile`에 연결한다. entries는 이미 확정된 (원문값, start/end) 목록이다. 반환은 (전체 원문값, start/end) 또는 None이다.
- [x] 2. `candidate_paired_review._field_summaries`의 이름 표현 진단을 RED→GREEN으로 맞춘다. 관련·전체 테스트 및 고정 H02 후보의 로컬 재투영을 확인한다.
- [x] 3. 독립 리뷰, diff 검사, commit/push·Linux CI와 검증 기록을 완료한다. 실행 중인 paired 비교는 원래 코드에서 끝까지 추적한다.

## 상태

이름 의미를 자동 확정하는 기능이 아니다. 실제 후보17개/고유2개의 null 탈락을 재현했고, 원문 표현을 확인용 값으로 보존하는 제한된 수정이다.

## 실행 기록

- 이전 목표 작업은 새 분기·명세·구현과 실패/통과 테스트를 남겼으므로 progress다. 직전 시간 추정 답변은 구현 진전이 아니며, 이번 재개는 실제 Git 상태와 종료된 비교 JSON을 다시 확인했다. 목표는 계속 active다.
- 작업1: 최초 8개 검사에서 구현 부재의 RED를 확인한 뒤 GREEN. 작업2: 비교 진단의 RED 1개를 추가해 새9건·관련24건 GREEN. 이번 재개에서는 아래 기존 테스트2건을 포함해35건 GREEN을 확인했다.
- 고정 H02의 원본·추출 해시와 승인 manifest 해시를 검증하고 같은 reviewed_refs를 이전/수정 코드에서 로컬 재투영했다. Solar 4/6→5/6, DeepSeek 5/6→6/6. 두 결과 모두 이름의 전체 인용 위치가 정확하고 needs_confirmation이며 다른9필드의 값·근거 digest는 전후 동일하다. 추가 API 호출은 없다. 전체 모델 품질 또는 독립 검증 결과로 일반화하지 않는다.
- Ruling: 전체857건 검사에서 기존 줄바꿈 테스트2건이 Windows checkout의 CRLF를 중복 변환하거나 LF 전용 파일을 가정해 실패했다. 실제 로더는 이미 LF 정규화를 한다. 두 테스트의 입력을 LF로 정규화한 뒤 CRLF를 생성하도록 수정했다. 평가 내용·해시·실제 로더는 바꾸지 않으며, 잘못 판단했을 경우 checkout 호환성을 검증하지 못할 수 있어 기존 두 테스트를 재실행해 GREEN을 확인했다.
- 전체 재검증857건(6건 건너뜀) 통과. 독립 리뷰의 수정 권고는 없었다. 리뷰가 보류한 의미적 동등성은 확인 필요로 남기고, H02 재생은 메인에서 직접 검증했다. 전체 품질은 미완료다.
- 코드2620207 및 비교 결과 문서c338659를 feature/source-name-expressions에 push했다. c338659의 Linux CI36630464051이 success임을 직접 조회했다. 비교 전용 브랜치에도 결과 문서d81dc53을 push했다. 기능 브랜치는 후속 품질 검증을 위해 보존하며 기본 서비스에 승격하지 않는다.
