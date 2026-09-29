# 구역 핵심 기능 선택 구현 계획

**브랜치:** `feature/section-feature-curation` (진단 브랜치 `fe1fa03` 기반)

**목표:** 30개를 넘는 내부 기능 후보에서 근거가 보존된 대표 후보를 선택형 단계로 좁혀, 안전한 Profile까지 도달하는지 실험한다.

## 작업 1 — 후보 수집과 ID 선택 계약

파일: `ai_service/agentfit_ai/section_feature_extraction.py`, `ai_service/tests/test_section_feature_extraction.py`

1. 31개 후보를 수집해도 공개 merge는 기존 오류를 유지하는 실패 테스트를 작성한다.
2. 구역 검증·정확 중복·상충을 공유하는 내부 수집 함수를 만들고, 후보 ID/값/제목 문맥을 모델에 전달하는 payload와 선택 ID 검증 함수를 분리한다.
3. 선택된 항목은 원래 selector를 그대로 원문 순서로 반환한다. 미지·중복·빈·31개 ID 및 비정상 구조를 거부한다.
4. 관련 테스트와 전체 테스트를 실행한다.

## 작업 2 — 호출 예산과 분석 흐름

파일: `ai_service/agentfit_ai/solar.py`, `ai_service/agentfit_ai/source_selector_analysis.py`, `ai_service/tests/test_source_selector_analysis.py`

1. 31개 이상일 때만 curation 호출 1회, 30개 이하는 0회를 확인하는 실패 테스트를 작성한다.
2. `request` 내부에 고정 stage `feature_curation`을 추가하고 명시적 훅으로 Solar 응답을 검증한다. 최대 19호출, 기존 모드 18호출 이하를 확인한다.
3. 선택 실패와 마지막 청크 실패에서 자동 완료가 불가능함을 테스트한다.

## 작업 3 — 평가 CLI와 안전 집계

파일: `ai_service/agentfit_ai/public_holdout_evaluation.py`, `ai_service/tests/test_public_holdout.py`

1. `--section-feature-curation`은 구역 추출과 선행 옵션을 요구하고 plan에 19호출을 기록하는 실패 테스트를 작성한다.
2. 평가 결과에 선택 전/후 개수만 허용 목록 정수로 기록하고 원문·후보 내용은 저장하지 않는 테스트를 작성한다.
3. 관련 테스트와 전체 테스트를 실행한다.

## 작업 4 — 실제 평가와 마무리

파일: `specs/ai-developer/04-analysis-provider/section-feature-curation/validation.md`

1. Campfire PRD 1건을 Solar로 1회 실행한다. 후보 수, 선택 수, 호출·시간, 최종 outcome, 부분 정답 7개, 미평가 값, 근거 오류를 기록한다.
2. 30개 이하로 내려가도 의미 검토가 이슈를 찾거나 정답이 누락되면 승격하지 않는다.
3. 전체 테스트, `git diff --check`, Linux CI와 독립 코드 리뷰를 확인한다. 중요 발견은 회귀 테스트 실패→수정→통과로 처리한다.
4. SDD 결과와 코드를 feature 브랜치에 커밋·push한다.
