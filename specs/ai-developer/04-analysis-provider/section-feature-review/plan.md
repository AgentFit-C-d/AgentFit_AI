# Section Feature Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검토 입력을 원문 구역으로 나눠 기능 누락을 끝까지 확인하고, 미검토 구역이 있으면 자동 완료를 막는다.

**Architecture:** 선택형 원문 선택자 분석기에서 A/B 필드 묶음은 유지한다. 서버가 원문 줄을 결정적으로 분할하고 기능 검토 요청·응답을 구역에 묶는다. 공통 분석 루프는 선택형 훅과 호출 상한만 확장하며 기본 경로는 그대로 둔다.

**Tech Stack:** Python 3, unittest, 기존 Solar/NVIDIA 호환 transport, 공개 PRD 평가 CLI

**Spec:** `specs/ai-developer/04-analysis-provider/section-feature-review/spec.md`

## Global Constraints

- 기본 `section_feature_review=False`, 공개 Profile·FastAPI·기본 Solar 경로 불변.
- 1청크 최대 120줄, 7청크 초과 시 모델 호출 전 실패, 검토 호출 포함 최대 12회.
- A/B 검토 뒤 기능 청크 전부를 검사하고, 유효 응답·정확한 줄 커버리지·이슈 없음이 자동 완료의 필요조건.
- 기능 청크 출력 최대 8,192토큰, 선택형 평가 전체 기한 600초.
- 진단과 평가 산출물에 원문·원본 응답·키·Profile을 기록하지 않는다.

## Review Focus

- 마지막 빈 줄과 CRLF 문서: 줄 ID가 빠지거나 중복되지 않아야 한다. Task 1 테스트.
- 제목 없는 840줄과 841줄: 각각 7청크 허용·8청크 모델 호출 전 보류. Task 1·3 테스트.
- 구역 밖 제목 문맥 및 missing 근거: 출력 근거는 커버 범위 안에서만 허용한다. Task 2 테스트.
- 두 구역에 걸친 동일 기능 항목: 같은 종류 이슈는 합치고 충돌은 보류한다. Task 2·3 테스트.
- 마지막 청크의 미완료 응답·시간 초과: 앞 청크가 성공해도 자동 완료하지 않는다. Task 3 테스트.

---

### Task 1: 결정적 구역 분할

**Files:**
- Create: `ai_service/agentfit_ai/section_feature_review.py`
- Test: `ai_service/tests/test_section_feature_review.py`

**Interfaces:**
- Produces: `split_feature_sections(document: str, *, max_lines: int = 120) -> tuple[tuple[int, int], ...]`. 각 `(start, end)`는 양끝 포함 원문 줄 ID이며 순서대로 정확히 1..N을 덮는다. `source_lines(document)`를 기준으로 Markdown `#`~`###` 제목 전에서 나누고 인접 단위를 최대 120줄로 탐욕 결합한다. 긴 단위는 줄로 분리한다.
- Produces: `validate_section_coverage(chunks: tuple[tuple[int, int], ...], line_count: int) -> None`. 빠짐·겹침·역순·120줄 초과에 `ValueError`.

- [ ] `test_section_splits_cover_every_line_once`와 Review Focus의 빈 줄·CRLF·제목 없는 840/841줄 테스트 작성.
- [ ] `rtk proxy ../.venv/Scripts/python.exe -m unittest discover -s tests -p test_section_feature_review.py -v` 실패 확인 (`ai_service`에서 실행).
- [ ] 위 인터페이스 구현. 제목은 경계의 첫 줄에 포함하고, 후행 빈 줄도 `source_lines`의 마지막 줄까지 포함.
- [ ] 같은 명령 통과 확인.
- [ ] 이 두 파일만 커밋.

### Task 2: 구역별 요청·응답 계약

**Files:**
- Modify: `ai_service/agentfit_ai/section_feature_review.py`
- Test: `ai_service/tests/test_section_feature_review.py`

**Interfaces:**
- Consumes: Task 1의 `(start, end)`.
- Produces: `section_review_payload(document, profile, chunk, *, model, effort, max_tokens=8192) -> dict`. 요청에 구역 원문·구역 밖 상위 제목 문맥·구역에 근거가 걸친 기능 항목과 전역 `item_ids`만 포함한다. schema는 `checkedRange: {start, end}`, `issues`를 요구하고 targetId·sourceLineIds를 해당 구역으로 제한한다.
- Produces: `normalize_section_review(reply, profile, document, chunk) -> dict`. 정확한 `checkedRange`, 허용 targetId, 원문 구역 내 missing 근거, 구역 안 기존 항목 근거, 중복을 검증하며 오류 시 `ReviewValidationError`를 발생시킨다. 정상 결과는 `{"issues": 기존 normalize_compact_review 형식의 목록}`이다.
- Produces: `merge_section_issues(issue_groups: list[list[dict]]) -> list[dict]`. 정규화된 동일 `field`·`itemIndex`·종류는 하나로 합치고 종류 충돌은 `ReviewValidationError`; missing은 근거 줄 ID와 종류가 같은 경우에만 합친다.

- [ ] 정상 payload의 구역 원문·문맥·전역 ID·8,192토큰, 정상 응답 및 Review Focus의 범위 밖 근거/targetId/중복·충돌 테스트 작성.
- [ ] 해당 테스트 실패 확인.
- [ ] 세 함수 구현. 기존 `item_ids`, `normalize_compact_review`, `_evidence_lines`를 재사용하되 원본 Profile 또는 기존 그룹 schema를 제자리 수정하지 않는다.
- [ ] 해당 테스트 통과 확인.
- [ ] 이 두 파일만 커밋.

### Task 3: 선택형 분석 루프와 안전 보류

**Files:**
- Modify: `ai_service/agentfit_ai/solar.py`
- Modify: `ai_service/agentfit_ai/source_selector_analysis.py`
- Test: `ai_service/tests/test_source_selector_analysis.py`
- Test: `ai_service/tests/test_section_feature_review.py`

**Interfaces:**
- Base hooks: `SolarAnalyzer._section_feature_chunks(document) -> tuple[tuple[int,int], ...] | None`, `_request_section_feature_review(document, profile, chunk, *, _trace=None, timeout=40)`, `_max_provider_calls() -> int`; 기본 구현은 각각 `None`, 안전 오류, `6`.
- Opt-in constructor: `SourceSelectorSolarAnalyzer(..., section_feature_review=False, ...)`; `True`는 `grouped_review=True`, `group_review_max_tokens=8192`와 함께만 허용. override hooks는 Task 1/2 계약을 호출하고 최대 호출 수 `12`를 돌려준다.
- 분석 루프는 첫 모델 호출 전 청크를 계산해 7개 초과를 보류한다. A/B 그룹만 기존 방식으로 검토하고 각 기능 청크를 `semantic_review`, `fields=["features"]`로 요청한다. 모든 응답·커버리지가 유효한 경우만 `_observe_review_issues`를 호출하고 완료 또는 `SEMANTIC_REJECTED`로 끝낸다. 실패 시 복구 초안은 확인 필요 또는 안전 실패다.

- [ ] 단일/여러 청크 완료, 유효 이슈 보류, 마지막 청크 실패, 최대 12호출, 8청크 사전 보류, 기본 최대 6호출 및 기존 grouped 경로 불변 테스트 작성.
- [ ] 해당 테스트 실패 확인.
- [ ] 세 hook과 최소한의 루프 분기 구현. `_request_section_feature_review`의 검증 오류는 기존 안전한 `SEMANTIC_REVIEW_INVALID` 경로로 변환한다.
- [ ] 관련 테스트 통과 확인.
- [ ] 변경 파일만 커밋.

### Task 4: 평가 CLI·검증·실험 기록

**Files:**
- Modify: `ai_service/agentfit_ai/public_holdout_evaluation.py`
- Test: `ai_service/tests/test_public_holdout.py`
- Create: `specs/ai-developer/04-analysis-provider/section-feature-review/validation.md`

**Interfaces:**
- CLI `--section-feature-review`는 `--source-selector --grouped-review --group-review-8k --accuracy-first --extended-review-window` 조합에서만 허용한다. `plan.json`에는 선택 여부, 최대 12호출, 600초, 기능 청크 출력 8,192토큰을 기록한다.

- [ ] CLI 선행조건, 안전한 plan/trace, 기본 평가 경로 불변 테스트 작성.
- [ ] 해당 테스트 실패 확인.
- [ ] CLI 연결 구현 후 관련 테스트와 전체 `rtk proxy ../.venv/Scripts/python.exe -m unittest discover -s tests -v` 통과 확인.
- [ ] Campfire 1건을 선택형 모드로 실행해 청크 완주·정답/정답 밖 값·부분 평가·호출 수를 기록한다. 유효할 때만 고정 튜닝 PRD 5건으로 확대한다. 새 독립 문서 및 Spring/Frontend 저장 금지 E2E는 미검증으로 명시한다.
- [ ] `validation.md`와 변경 파일만 커밋·push하고 Linux CI 결과를 확인한다.
