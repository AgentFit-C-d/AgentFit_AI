# Section Review Model Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 동일한 검증 초안·원문 구역에서 Solar 추론 설정과 NVIDIA 검토 모델의 완료·형식 유효성을 비교한다.

**Architecture:** 첫 단계 Profile을 관측 훅으로 메모리에만 잡고, 기존 section review payload와 공통 검증기를 모든 비교군에 재사용한다. 결과는 안전 메타데이터만 기록한다.

**Tech Stack:** Python, `unittest`, 기존 Solar/NVIDIA transport.

**Spec:** `specs/ai-developer/04-analysis-provider/section-review-model-probe/spec.md`

## Global Constraints

- 공개 Profile·기본 서비스·FastAPI 동작은 변경하지 않는다.
- 원문·초안·키·원본 응답은 출력·파일·로그에 저장하지 않는다.
- 실제 호출은 `--live`가 있을 때만 하고 고정 공개 튜닝 문서 1건만 쓴다.

## Review Focus

- 검증 초안 확보 실패 시 비교 호출 없이 안전 실패한다.
- 서로 다른 비교군도 동일 원문·초안·구역·JSON schema를 사용한다.
- 응답 미완료·형식 오류·제공자 오류가 결과 파일에 원본 내용을 남기지 않는다.
- 결과 경로 재사용 시 덮어쓰기 전에 거부한다.
- 모델 이름·오류 코드는 허용 목록 밖 문자열을 기록하지 않는다.

---

### Task 1: 일시적 초안 획득과 단일 구역 검증

**Files:**
- Create: `ai_service/agentfit_ai/section_review_model_probe.py`
- Test: `ai_service/tests/test_section_review_model_probe.py`

**Interfaces:** `capture_draft(document, document_id, key, transport) -> profile`; `evaluate_section(document, profile, chunk, sender, payload) -> safe dict`.

- [ ] 합성 문서에서 검토 전 초안을 얻고 검토 제공자 호출을 하지 않는 실패 테스트를 작성한다.
- [ ] 같은 구역 응답의 정상/미완료/검증 오류를 안전 수치만으로 반환하는 실패 테스트를 작성한다.
- [ ] 예상 실패 확인 후 기존 훅·검증기를 재사용해 구현하고 관련 테스트를 통과시킨다.

### Task 2: CLI와 비교군 실행

**Files:**
- Modify: `ai_service/agentfit_ai/section_review_model_probe.py`
- Test: `ai_service/tests/test_section_review_model_probe.py`

- [ ] `--live`·고정 케이스·구역 번호·결과 경로 검증과 출력 금지 필드 테스트를 작성한다.
- [ ] Solar 3설정 및 NVIDIA 3모델의 동일 payload 비교를 구현한다. 모델별 오류 후에도 나머지를 평가한다.
- [ ] 관련·전체 테스트와 `git diff --check`를 실행한다.

### Task 3: 실제 비교와 검증

**Files:**
- Create: `specs/ai-developer/04-analysis-provider/section-review-model-probe/validation.md`

- [ ] Campfire 12번째 50줄 구역에서 각 비교군을 1회 실행해 안전 수치만 기록한다.
- [ ] 완료·검증된 후보와 한계, 다음 전체 평가 관문을 판단한다.
- [ ] Linux CI와 독립 코드 리뷰를 확인하고 `feature/section-review-model-probe`에 커밋·push한다.
