# Section Feature Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 긴 원문에서 기능 추출을 모든 구역에 분산하고 서버가 후보를 통합해 기능 누락의 변동을 줄이는지 평가한다.

**Architecture:** 기존 source selector의 core 추출과 묶음·구역 검토는 유지한다. 기능 추출 요청만 구역별로 보낸 뒤, 각 응답의 줄 ID·selector·role을 서버가 검증하고 원문 순서로 통합한다.

**Tech Stack:** Python 3, unittest, Solar/NVIDIA 호환 transport, 기존 공개 PRD 평가 CLI

**Spec:** `specs/ai-developer/04-analysis-provider/section-feature-extraction/spec.md`

## Global Constraints

- 기본 `section_feature_extraction=False`; 공개 Profile·FastAPI·기본 분석기 불변.
- 기존 최대 120줄·7청크 전체 커버리지와 구역 밖 줄 선택 금지.
- 중복은 정확히 같은 값만 제거하고 다른 값을 부분문자열로 묶지 않는다. confirmed/absent 충돌·30개 초과·미검토 청크는 자동 완료 금지.
- 선택형 최대 18호출, 평가 전체 1,200초. 원문·원본 응답·키·Profile 진단 저장 금지.
- 이미 사용한 공개 PRD는 튜닝 자료이며 서비스 승격 근거가 아니다.

## Review Focus

- 동일한 짧은 값이 다른 긴 값의 일부인 문서: 두 후보를 모두 유지한다. Task 1.
- 제목 문맥에만 있는 기능과 청크 밖 줄 ID: 후보로 받지 않는다. Task 1.
- 마지막 청크가 실패하거나 31개 고유 기능이 나오면 안전 실패한다. Task 1·2.
- confirmed와 absent가 서로 다른 청크에서 나오면 보류한다. Task 1·2.
- 기존 단일 기능 추출과 6/12호출 경로는 변경되지 않는다. Task 2·3.

---

### Task 1: 구역 기능 추출 응답과 서버 통합

**Files:**
- Create: `ai_service/agentfit_ai/section_feature_extraction.py`
- Test: `ai_service/tests/test_section_feature_extraction.py`

**Interfaces:**
- Produces: `section_extraction_payload(document, chunk, *, model) -> dict`. 기존 source selector의 `features` schema와 프롬프트를 사용하되 입력은 구역 원문과 읽기 전용 상위 제목 문맥뿐이며 `lineId`는 `chunk` 범위로 제한한다. 추출 출력 상한 4,096토큰.
- Produces: `normalize_section_features(document, chunk, reply) -> dict | None`. 응답 `{features: null|confirmed|absent}`에서 모든 `lineId`, selector, role, 선택 값과 구역을 검증한다. 오류는 고정 코드의 `EvidenceError`로 반환한다.
- Produces: `merge_section_features(document, chunks, replies) -> dict | None`. 청크 순서의 `confirmed.items`를 실제 선택 값으로 정확 중복 제거한다. 모든 null이면 null, absent만 있으면 첫 부재 근거, confirmed/absent 충돌 또는 30개 초과면 `EvidenceError`.

- [ ] 정상 구역 payload, 청크 밖 줄/제목 거부, 짧은 값과 긴 값 구분, 중복·absence 충돌·31개 상한 테스트를 먼저 작성한다.
- [ ] `rtk proxy ../.venv/Scripts/python.exe -m unittest discover -s tests -p test_section_feature_extraction.py -v` 실패를 확인한다 (`ai_service`에서 실행).
- [ ] 위 세 함수 구현 후 같은 명령과 전체 테스트를 통과시킨다.
- [ ] 해당 두 파일만 커밋한다.

### Task 2: 선택형 최초 분석 호출 연결

**Files:**
- Modify: `ai_service/agentfit_ai/solar.py`
- Modify: `ai_service/agentfit_ai/source_selector_analysis.py`
- Modify: `ai_service/agentfit_ai/section_feature_extraction.py`
- Test: `ai_service/tests/test_source_selector_analysis.py`
- Test: `ai_service/tests/test_section_feature_extraction.py`

**Interfaces:**
- Base hook: `SolarAnalyzer._request_section_features(document, chunk, *, _trace=None, timeout=40)`는 기본적으로 안전 실패. 기존 내부 `request(..., source_section=None)`이 명시된 경우에만 hook을 호출한다.
- 기존 `_first_pass(request, reserve_call)` 시그니처와 병렬 모드를 보존하기 위해 base `_first_pass_with_sections(document, request, reserve_call, chunks)`를 경유한다. 기본 구현은 기존 `_first_pass`를 호출한다.
- `SourceSelectorSolarAnalyzer(..., section_feature_extraction=False, ...)`는 `section_feature_review=True`와 8K grouped 모드에서만 활성화한다. 선택형 `_first_pass_with_sections`는 core 1회, 각 청크 features 1회, Task 1의 통합을 반환한다. `_max_provider_calls()`는 이 모드에서 18이다.
- 마지막 청크 실패 및 병합 오류에서 Profile을 완성하거나 검토 완료로 표시하지 않는다. 기존 근거 구조 수정 1회와 A/B·모든 기능 청크 검토는 그대로 둔다.

- [ ] 2청크 정상 통합, 마지막 실패·absence 충돌·18호출 상한, 기존 모드 불변 테스트를 작성해 실패를 확인한다.
- [ ] 두 파일에 hook·옵트인·호출 루프를 연결하고 관련 및 전체 테스트를 통과시킨다.
- [ ] 변경 파일만 커밋한다.

### Task 3: 평가 CLI와 안전 집계

**Files:**
- Modify: `ai_service/agentfit_ai/public_holdout_evaluation.py`
- Test: `ai_service/tests/test_public_holdout.py`

**Interfaces:**
- `--section-feature-extraction`은 `--section-feature-review`와 그 선행 옵션이 모두 있을 때만 허용한다. 선택 시 `plan.json`에 모드, 최대 18호출, 전체 1,200초, 구역 추출 4,096토큰을 기록한다. 기존 옵션의 기록은 유지한다.

- [ ] 옵션 선행조건, 안전한 plan 기록, 기존 600초 경로 불변 테스트를 먼저 작성하고 실패를 확인한다.
- [ ] CLI 연결 후 관련 및 전체 테스트를 통과시킨다.
- [ ] 변경 파일만 커밋한다.

### Task 4: 실제 튜닝 문서·독립 리뷰

**Files:**
- Create: `specs/ai-developer/04-analysis-provider/section-feature-extraction/validation.md`

- [ ] 같은 Campfire 튜닝 문서 1건을 새 옵션으로 실행한다. 구조 검증·부분 정답 7개·미평가 값·호출 수·의미 검토 상태를 이전 실행과 함께 기록하되 단일 실행 차이를 인과 효과로 주장하지 않는다.
- [ ] 결과가 유효하고 개선될 때 추가 문서 전송은 별도 승인 조건을 확인한다. 실패해도 `validation.md`에 분류하고 기본값은 유지한다.
- [ ] 전체 테스트, `git diff --check`, Linux CI와 독립 코드 리뷰를 확인한다. 중대한 발견은 회귀 테스트 실패→수정→통과로 처리한다.
- [ ] 검증 문서와 수정 사항을 `feature/section-feature-extraction`에 커밋·push한다.
