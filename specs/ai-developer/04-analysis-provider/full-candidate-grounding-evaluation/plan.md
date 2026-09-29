# 전체 후보 근거 평가 구현 계획

> **실행:** 기존 선택형 평가기 위에 독립 채점기를 추가한다. 각 작업은 실패 테스트→최소 구현→관련 테스트 순서로 진행한다.

**목표:** 합성 PDF 문서의 모든 추출 후보를 골드와 대조해 목표 후보 밖의 오확정까지 측정한다.

**구조:** 기존 Docling 변환·LangExtract 추출·Solar 분류·규칙 검증을 재사용한다. 새 평가 모듈은 문서 단위 골드 매핑, 전체 후보 채점, 안전 집계를 담당한다.

**파일:** `ai_service/agentfit_ai/full_candidate_grounding_evaluation.py`, `ai_service/tests/test_full_candidate_grounding_evaluation.py`, 이 폴더의 `cases.json`·`validation.md`.

## 1. 전체 후보 채점

- [x] 추가 후보가 자동 허용되면 목표 후보가 모두 맞아도 오확정으로 집계되는 실패 테스트를 썼다.
- [x] 반복 이름의 다른 등장, 중복 후보, 필드 오류, 비확정 상태의 보류 테스트를 썼다. 모호한 문맥은 기존 grounding 테스트와 평가 실패 처리에 의존한다.
- [x] 기존 grounding·guard 함수로 `score_document`를 구현하고 원문 없는 문서별 수치를 반환한다.

## 2. 고정 PDF 평가기

- [x] 네 문서의 모든 허용 근거를 작성하고 파일 SHA-256을 모델 호출 전에 고정했다. LF/CRLF에서 같은 내용으로 검증한다.
- [x] PDF 변환 후 모든 골드의 고유 구간·페이지를 선검증하는 테스트를 썼다.
- [x] `--live`와 fixture 확인 뒤에만 키를 읽는 CLI를 만들고 변환·추출·분류 실패를 안전 코드로 기록한다.

## 3. 실제 평가와 검증

- [x] 고정 합성 문서에 표준 Docling 경로를 반복 실행하고 native/pypdf와 비교했다. 기존 분류 지시문의 불안정성을 확인해 필드 정의를 추가했다.
- [x] 서비스 전체 테스트, 실험 venv의 실제 Docling 테스트, Linux CI와 diff 검사를 실행했다.
- [x] 결과·남은 관문을 `validation.md`에 기록하고 `feature/full-candidate-grounding-evaluation`을 push했다.
