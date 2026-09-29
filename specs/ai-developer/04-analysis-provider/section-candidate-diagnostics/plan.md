# 구역 기능 후보 과다 진단 구현 계획

**목표:** 내용 비저장 숫자 집계로 구역별 기능 후보 과다의 위치와 중복 정도를 확인한다.

**분기:** `feature/section-candidate-diagnostics` (구역별 기능 추출 브랜치에서 분기)

## 작업 1 — 서버 통합 훅

파일: `ai_service/agentfit_ai/section_feature_extraction.py`, `ai_service/agentfit_ai/source_selector_analysis.py`, `ai_service/tests/test_section_feature_extraction.py`

1. 합성 응답에서 구역별 개수·총수·중복·고유 수를 확인하고 31개 초과 때도 관측 훅이 호출되는 실패 테스트를 먼저 작성한다.
2. `merge_section_features(..., observer=None)`에서 정규화와 정확 중복 계산 후 상한 검사 전에 고정 스키마 숫자 집계를 observer에 전달한다. SourceSelector 분석기는 기본 no-op `_observe_section_feature_candidates` 훅을 넘긴다.
3. 관련 테스트와 전체 테스트를 실행한다.

## 작업 2 — 평가기의 안전 출력

파일: `ai_service/agentfit_ai/public_holdout_evaluation.py`, `ai_service/tests/test_public_holdout.py`

1. 숫자 범위와 키 허용 목록, 비밀 값 누락, 미완료 집계 버리기를 재현하는 테스트를 먼저 작성한다.
2. `_SafeTraceMixin`의 훅이 숫자 집계만 메모리에 보관하고 `evaluate_case` 결과에 기록한다. 다른 실험에는 키를 추가하지 않는다.
3. 관련 테스트와 전체 테스트를 실행한다.

## 작업 3 — 실제 문서 검증과 마무리

파일: `specs/ai-developer/04-analysis-provider/section-candidate-diagnostics/validation.md`

1. Campfire PRD 1건을 같은 Solar 옵션으로 실행한다. 안전한 결과에서 후보 개수·중복 수·결과 코드를 기록한다.
2. 검증 결과가 한 구역에 집중되는지, 여러 구역에 고르게 쌓이는지 분석한다. 정답성은 수치로 단정하지 않는다.
3. `git diff --check`, 전체 테스트, Linux CI, 독립 리뷰를 확인하고 기능 브랜치에 커밋·push한다. 기존 선택형 모드는 승격하지 않는다.
