# Capability Source Occurrences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Direct implementation is already authorized.

**Goal:** 긴 anchor 복사 없이 기능 후보를 원문의 모든 정확한 등장 위치로 복원하고 기존 독립 분류에 연결한다.
**Architecture:** 새 quote-only 추출 모듈은 기존 sender/schema/position 확장을 사용한다. 통합 파이프라인의 bool 선택 옵션으로 기존 동작 추출을 교체하고 이후 경로는 공유한다.
**Tech Stack:** Python unittest, 기존 NVIDIA/OpenAI 호환 transport, LangExtract 통합 경로.
**Spec:** [spec.md](spec.md)

## Global Constraints

- 최대60인용/인용200 Unicode code points/고유 위치240개, 엄격 shape와 원문 일치.
- 공개 Profile·기본 HTTP 서비스·이전 freeze는 유지. `capability_candidates=False` 기본값.
- 요청당64호출 공유 meter, NVIDIA 단독 경로 재시도0(기존 혼합 경로의 호출자 설정 유지), 실패 시 fallback0. 구현·로컬 테스트 외부0.
- Python E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe. 모든 shell은 rtk. 각 로컬 suite180초 상한,90분마다 체크포인트.
- 사용자 자율 SDD 승인 적용. 기능 브랜치 commit/push, merge/배포/삭제 없음. 기존 scratch 보존.

## Review Focus

1. 한 인용이 정상/부정/다른제품 문맥에 반복: 모든 위치와 독립 판단 보존(Task1,2).
2. 흔한 짧은 인용으로240개 초과: 부분 결과/조용한 절단 없이 실패(Task1,2).
3. 원문 부재·중복 quote: 부재 거절 보존, 중복 인용은 동일 span을 중복 생산하지 않음(Task1).
4. 옵션 오타·bool 대신1/None: 네트워크 전에 거절, 기존 기본 경로 유지(Task2).
5. 제공자 실패·호출 예산 부족: 고정 단계와 meter 유지, 추가 호출/fallback 없음(Task2).

### Task 1: Quote-only 기능 후보 추출

**Files:** Create `ai_service/agentfit_ai/capability_candidates.py`; test `ai_service/tests/test_capability_candidates.py`.
**Interfaces:** Consumes `_sender`, `_payload`, `freeze_candidate_occurrences`, `_validate_frozen`; produces `extract_capability_candidates(document, key, *, model=MODEL, transport=None) -> {'candidates': list, 'rejected': list}`.

- [x] Write failing tests: Unicode 반복 위치(2,15 등)와 정확 ID, 원문 없는 quote 거절, 동일 quote 중복 제거,240/241 경계,60/61 quote 및200/201문자 경계, malformed/top-level extras/provider error/empty results, invalid input blocks transport. 출력에 quote/key 없음도 확인한다.
- [x] Run `python -m unittest discover -s tests -p test_capability_candidates.py -v` in ai_service. Expected: missing implementation failures.
- [x] Implement strict quote-only response validation and existing position expansion. No field/status 판단, normalization, extra calls.
- [x] Run same tests. Expected: all pass. Then full unit suite with180초 process bound; output tail 기록.
- [x] Commit `feat: ground capability quotes at all source occurrences`; task-done same focused test command.

### Task 2: 선택형 통합 경로

**Files:** Modify `ai_service/agentfit_ai/candidate_analysis_pipeline.py`; create `ai_service/tests/test_capability_candidate_pipeline.py`.
**Interfaces:** Consumes Task1 extractor. Adds keyword `capability_candidates=False` to `analyze_integrated_candidates` and `analyze_nvidia_candidates`; strict bool and shared meter.

- [x] Write failing full-path tests with fake provider only: same quote in current/negated/other contexts preserves evidence for confirmed occurrence; absent quote forces confirmation; invalid bool prevents calls; occurrence limit fails correct stage; provider/call budget stops without fallback; default operation path unchanged and NVIDIA wrapper option reaches real pipeline.
- [x] Run `python -m unittest discover -s tests -p test_capability_candidate_pipeline.py -v`. Expected: unsupported option failures.
- [x] Add option validation, select extractor at OPERATION_EXTRACTION_FAILED, forward NVIDIA option. Reuse all subsequent stages.
- [x] Run focused tests and existing candidate pipeline/NVIDIA tests; then full unit/runtime/contract/core suites, each180초 process bound. Expected: all pass with documented platform skips only.
- [x] Commit `feat: opt in to capability occurrence extraction`; task-done focused tests.

## Finalization

One fresh gpt-6-astra/high reviewer checks the complete branch (no implementation agents). Fix Important/Critical with RED→GREEN once, run affected gates, commit/push and inspect exact CI. Preserve scratch and previous evidence. Write validation/review records. Register separate immutable full-path probe only after these gates; never describe local test success as model quality improvement.
