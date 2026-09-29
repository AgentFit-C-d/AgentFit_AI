# Fine Feature Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선택형 기능 의미 검토를 50줄 이하 구역으로 나눠 출력 상한 실패를 검증한다.

**Architecture:** 분석기는 추출 구역과 검토 구역을 별도 훅으로 계산한다. 기존 추출 호출은 120줄 구역을 사용하고, 의미 검토만 50줄 구역을 사용한다. 서버가 두 커버리지와 호출 예산을 각각 검증한다.

**Tech Stack:** Python, `unittest`, 안전 평가 CLI.

**Spec:** `specs/ai-developer/04-analysis-provider/fine-feature-review/spec.md`

## Global Constraints

- 기본 분석기·공개 Profile·FastAPI 계약·기존 추출 구역 120줄/7개는 변경하지 않는다.
- 새 모드는 `fieldwise_review=True`와 함께 최대 21개 검토 구역·36호출·2,400초다.
- 평가 파일에는 원문·원본 응답·키·Profile 내용을 저장하지 않는다.

## Review Focus

- 추출과 검토의 구역 수가 달라도 같은 원문 전체를 빠짐없이 덮는다.
- 검토 22번째 구역은 호출 전에 거부하며 일부 검토로 자동 완료하지 않는다.
- 마지막 검토 구역의 미완료·잘못된 범위는 자동 완료 금지다.
- 최대 36번째 호출도 예약·실행 가능하며 37번째 호출은 거부한다.
- 기본 120줄 구역·1,200초 설정은 새 옵션 없이 그대로다.

---

### Task 1: 독립 검토 구역과 호출 예산

**Files:**
- Modify: `ai_service/agentfit_ai/solar.py`, `ai_service/agentfit_ai/source_selector_analysis.py`
- Test: `ai_service/tests/test_source_selector_analysis.py`, `ai_service/tests/test_section_feature_review.py`

**Interfaces:** `SolarAnalyzer._feature_review_chunks(document, extraction_chunks)`; `SourceSelectorSolarAnalyzer(..., fine_feature_review=False)`.

- [ ] 120줄 추출/50줄 검토 분리, 최대 21개 사전 거부, 마지막 검토 실패와 36회 예산의 실패 테스트를 작성한다.
- [ ] 관련 테스트를 실행해 예상 실패를 확인한다.
- [ ] 검토 구역 훅과 반복 루프, 모드 검증·호출 예산을 구현한다.
- [ ] 관련 테스트와 전체 테스트를 실행한다.

### Task 2: 선택형 기한과 평가 CLI

**Files:**
- Modify: `ai_service/agentfit_ai/solar.py`, `ai_service/agentfit_ai/source_selector_analysis.py`, `ai_service/agentfit_ai/public_holdout_evaluation.py`
- Test: `ai_service/tests/test_source_selector_analysis.py`, `ai_service/tests/test_public_holdout.py`

**Interfaces:** `--fine-feature-review`; plan의 `fine_feature_review`, `feature_review_max_lines=50`, `max_provider_calls=36`, `analysis_timeout_seconds=2400`.

- [ ] 2,400초 선택형 허용과 기존 1,200초 상한, CLI 선행 플래그·plan 전달의 실패 테스트를 작성한다.
- [ ] 예상 실패를 확인하고 옵션 검증·plan·분석기 연결을 구현한다.
- [ ] 관련 테스트와 전체 테스트를 실행한다.

### Task 3: 실제 평가와 브랜치 검증

**Files:**
- Create: `specs/ai-developer/04-analysis-provider/fine-feature-review/validation.md`

- [ ] Campfire 1건 live 평가를 실행하고 14개 기능 검토 구역의 완주 여부와 안전 수치를 기록한다.
- [ ] 부분 정답·미정 보존·정답 밖 값에서 서비스 승격 가능성을 따로 평가한다.
- [ ] 전체 테스트, `git diff --check`, Linux CI, 독립 코드 리뷰를 확인한다.
- [ ] 명세·계획·코드·검증을 `feature/fine-feature-review`에 커밋하고 push한다.
