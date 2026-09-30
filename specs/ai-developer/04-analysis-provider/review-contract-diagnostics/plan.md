# 검토 계약 오류 진단 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 의미 검토를 완주하지 못한 이유를 민감 내용 없이 구분한다.

**Architecture:** 기존 후보/근거 검증 predicate를 유지하고 실패 시에만 순수 진단 함수를 실행한다. 기존 선택형 review_calls에 고정 코드 또는 None을 저장한다.

**Tech Stack:** Python, unittest, 기존 Solar/NVIDIA transport.

**Spec:** specs/ai-developer/04-analysis-provider/review-contract-diagnostics/spec.md

## Global Constraints

- 공개 Profile·요청·수락 조건·예외·의미 실패 처리·64회 예산·전송 재시도 1회를 유지한다.
- 원문·응답 본문·값·인용·키를 진단에 기록하지 않는다.
- 기존 checkout을 재사용하고 feature/review-contract-diagnostics에 push한다. 다른 checkout과 개인 문서 발췌는 건드리지 않는다.
- 직접 구현과 독립 최종 리뷰를 적용한다. 사용자 자율 승인으로 재승인을 요청하지 않는다.

## Review Focus

- 여러 조건이 동시에 어긋난 응답: 명세의 순서로 하나의 원인만 기록하고 기존 거절 유지.
- JSON 중첩 목록/객체 등 unhashable 항목: 진단이 원래 실패를 가리지 않아야 한다.
- reasoned_review=False와 collector=None: 기존 요청·결과·실패를 유지.
- 파서가 거절한 top-level 계약/JSON: 의미 검토 실패와 혼동하지 않아야 한다.
- 늦은 batch 실패: 앞서 성공한 기록 보존, 이후 coverage/투영/재시도 금지.

### Task 1: 선택형 검토 진단과 회귀 검증

**Files:**
- Modify: ai_service/agentfit_ai/candidate_split_review.py
- Create: ai_service/tests/test_review_contract_diagnostics.py
- Create: specs/ai-developer/04-analysis-provider/review-contract-diagnostics/validation.md
- Create: work/harness/review-contract-diagnostics/STATE.md

**Interfaces:**
- Consumes: review_candidates_separately(..., review_calls=None, reasoned_review=False), 기존 ProviderFixture.
- Produces: 새 review_calls 행의 contract_issue: str | None. 기존 반환/예외 계약은 동일.

- [x] **Step 1: 테스트 작성**

테스트 이름과 주요 기대값:
`test_candidate_list_violations_are_distinct`: 목록 타입/멤버/중복/누락/순서를 독립 fixture로 주고 고정 코드와 INVALID_REVIEW_CONTRACT, 요청 1회 확인.
`test_rejection_reason_violations_are_distinct`: 사유 타입/개수/행/ID/enum/중복을 구분. 잘못된 원문 문자열은 기록되지 않음.
`test_coverage_violations_are_distinct`: 후보 없는 문서에서도 checkedFields/missingFields 오류 구분.
`test_valid_collector_is_observational`: None/[]/기존 행 collector에서 payload와 결과 동일, 성공 code=None.
`test_provider_and_parser_failures_keep_original_error`: INVALID_RESPONSE, PROVIDER_MODEL, INCOMPLETE_RESPONSE, PROVIDER_UNAVAILABLE는 원래 오류와 code=None.
`test_late_failure_stops_integrated_pipeline`: 2번째 후보 batch에서 reason 오류, 앞선 행 유지, projected 없음, semantic retry 없음.

- [x] **Step 2: RED 확인**

Run (ai_service): `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_review_contract_diagnostics.py -q`
Expected: contract_issue 누락으로 실패. 기존 실패 처리에 관한 assertion은 통과.

- [x] **Step 3: 최소 구현**

같은 모듈에 `_sequence_issue(value, allowed, *, complete) -> str | None`, `_candidate_contract_issue(result, ids, reasoned_review) -> str`, `_coverage_contract_issue(result) -> str` 추가. 고정 코드만 반환하고 입력 불변 유지. 내부 send에 진단 callback을 연결하고 collector가 존재하며 기존 predicate가 False일 때만 호출. 기존 predicate와 payload 그대로 유지.

- [x] **Step 4: GREEN 및 전체 회귀**

Run: Step2 명령. Expected: 신규 테스트 모두 통과.
Run (ai_service): `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q`
Expected: 실패 0, 기존 플랫폼 skip 6. 이 명령을 task-done 최종 검증으로 사용.

- [x] **Step 5: 검증 기록 및 구현 commit**

기준 e544650, RED/GREEN/전체 결과와 한계 기록. 지정 파일만 stage/commit. Expected: 제품 변경과 테스트·문서만 포함.

## 최종 검증 및 후속 평가

Task1 완료 후 독립 전체 리뷰 1회, Important 이상은 RED→GREEN 수정 1회와 전체 회귀. 리뷰 뒤 고정 revision으로 H02 드라이버를 새 경로에 준비해 API 0 사전검사 후 한 번 평가한다. 기존 결과·해시와 분모를 감사하며 코드 변경 여부와 진단 고정 코드 집합을 검증한다. 실제 평가 문서만 추가해 push하고 정확한 구현 커밋 CI를 확인한다. 기존 SDD ledger는 사용자 맥락 유지 지침에 따라 보존한다.
