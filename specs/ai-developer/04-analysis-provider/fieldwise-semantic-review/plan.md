# Fieldwise Semantic Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선택형 분석의 B 묶음을 필드별로 검토해 8,192토큰 미완료를 줄이고 전 필드 검토 완료 계약을 유지한다.

**Architecture:** 기존 그룹 검토 payload와 정규화를 재사용한다. 선택형 플래그는 A 묶음과 B의 4개 단일 필드 묶음을 반환하며 서버의 전체 필드 커버리지 검증과 기능 구역 검토를 통과해야 완료한다.

**Tech Stack:** Python, `unittest`, FastAPI와 분리된 평가 CLI.

**Spec:** `specs/ai-developer/04-analysis-provider/fieldwise-semantic-review/spec.md`

## Global Constraints

- 기본 분석기, 공개 Profile, FastAPI 계약은 바꾸지 않는다.
- 새 모드는 `section_feature_curation=True`일 때만 켜며 최대 22회·1,200초다.
- 평가 기록에는 원문·원본 응답·키·Profile 내용을 저장하지 않는다.

## Review Focus

- 검토 필드 누락·중복: 전체 필드 커버리지 실패이며 자동 완료 금지.
- 다른 필드의 오류를 한 필드에 섞은 응답: 형식 오류로 보류.
- 마지막 단일 필드 또는 마지막 기능 구역의 미완료: 이전 성공으로 자동 완료 금지.
- 첫 묶음 오류와 후속 정상 응답: 최종 `needs_confirmation` 및 안전한 이슈 합산.
- 22회 예산: 최대 청크·수정·선택에서도 마지막 구역을 검토할 수 있어야 한다.

---

### Task 1: 묶음 계약과 분석 흐름

**Files:**
- Modify: `ai_service/agentfit_ai/grouped_review.py`, `ai_service/agentfit_ai/source_selector_analysis.py`, `ai_service/agentfit_ai/solar.py`
- Test: `ai_service/tests/test_grouped_review.py`, `ai_service/tests/test_source_selector_analysis.py`

**Interfaces:** `FIELDWISE_GROUPS: tuple[tuple[str, ...], ...]`; `SourceSelectorSolarAnalyzer(..., fieldwise_review=False)`.

- [ ] 한 필드의 payload·정규화와 여섯 묶음 완주·실패·22회 예산에 대한 실패 테스트를 작성한다.
- [ ] 관련 테스트를 실행해 새 계약이 없어서 실패하는지 확인한다.
- [ ] 필드별 묶음과 선택형 연결을 구현하고 루프의 검토 그룹 수를 고정 3에서 선택된 그룹 수로 바꾼다.
- [ ] 관련 테스트와 전체 `unittest discover -s tests -q`를 실행한다.

### Task 2: 평가 CLI와 안전한 plan

**Files:**
- Modify: `ai_service/agentfit_ai/public_holdout_evaluation.py`
- Test: `ai_service/tests/test_public_holdout.py`

**Interfaces:** `--fieldwise-semantic-review`; plan의 `fieldwise_semantic_review: bool`, `max_provider_calls: 22`.

- [ ] 선행 플래그 거부와 정상 CLI 옵션·plan·분석기 인자에 대한 실패 테스트를 작성한다.
- [ ] 관련 테스트의 예상 실패를 확인한다.
- [ ] 옵션 검증·plan·분석기 전달을 구현한다.
- [ ] 관련 테스트와 전체 테스트를 실행한다.

### Task 3: 실제 평가와 브랜치 검증

**Files:**
- Create: `specs/ai-developer/04-analysis-provider/fieldwise-semantic-review/validation.md`

- [ ] Campfire PRD 1건에 대해 1회 live 평가를 실행하고 안전 집계로 이전 실행과 비교한다.
- [ ] 평가가 완주하면 부분 정답과 정답 밖 값을 검토하고, 불완전하면 실패 단계와 후속 원인을 기록한다.
- [ ] `git diff --check`, 전체 테스트, Linux CI를 확인한다. 실서비스 승격은 독립 자료와 저장 전 확인 E2E까지 보류한다.
- [ ] 명세·계획·구현·검증을 `feature/fieldwise-semantic-review`에 커밋하고 push한다.
