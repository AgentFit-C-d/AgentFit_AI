# DeepSeek 추론량 명시 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 기존 직접 구현 및 목표 내 자율 진행 권한을 적용한다.

**Goal:** 출력 계약을 보존한 off/on25 비교로 현재 실패의 감소 여부를 검증한다.

**Architecture:** 기존 평가 모듈에 선택 인자와 안전한 메타데이터만 추가한다. 고정된 로컬 실행기는 사전 검증 후 합성 gate와 조건부 H02를 실행한다.

**Tech Stack:** Python 3.13, unittest, 기존 NVIDIA transport.

**Spec:** specs/ai-developer/04-analysis-provider/deepseek-review-effort/spec.md

## Global Constraints

- feature/deepseek-review-effort. 기본 서비스/공개 Profile/공유 환경 변경 없음.
- 합성4+조건부H0214=최대18호출. 기존 정답·snapshot 불변. 개인정보 출력 금지.
- 설정은 요청값이며 제공자 내부 적용 보장 없음. 실패는 미평가, 독립 검증/서비스 완성과 구분.

## Review Focus

1. bool/float/범위 밖 추론량이 첫 호출 전에 거부되고 None 기본 요청이 그대로인가.
2. 추론량은 True arm에만 전달되며 양쪽 상세 schema와 서버 검증이 유지되는가.
3. 보고서가 요청 설정과 제공자 적용 사실을 혼동하거나 실패를 정확도 분모에 넣지 않는가.
4. 합성 gate·코드 hash·호출 상한·원문/키/추론 비공개·고정 정답이 실제 실행기와 결과에서 지켜지는가.
5. 20개 합성 및 튜닝된 H02 결과를 서비스 품질이나 일반화 증거로 과장하지 않는가.

### Task 1: 추론량 선택 옵션과 한정 평가

**Files:**
- Modify: ai_service/agentfit_ai/candidate_thinking_evaluation.py
- Test: ai_service/tests/test_candidate_thinking_evaluation.py
- Create: specs/ai-developer/04-analysis-provider/deepseek-review-effort/validation.md
- Create: work/harness/deepseek-review-effort/STATE.md
- Local ignored: E:/AgentFit/tmp/run-deepseek-effort-h02-v1.py 및 별도 결과

**Interfaces:**
- Consumes: 기존 evaluate_thinking_reviews와 snapshot/score/transport 계약.
- Produces: thinking_effort=None 선택 인자, settings.thinking_effort_requested 및 arm.reasoning_effort_requested.

- [ ] Step 1: explicit25 True 전용 전달/메타데이터, 잘못된 값 API0, 1·100·None 호환 테스트를 작성한다. focused unittest에서 새 인자 TypeError를 RED로 확인한다.
- [ ] Step 2: 최소 구현 후 focused unittest를 실행한다. Expected: 기존10+신규3 모두 통과.
- [ ] Step 3: 별도 드라이버를 준비한다. 고정 helper/hash를 확인하고 20개 합성 gate 및 H02 preflight를 실행한다. Expected: 합성20/정답20/4호출, H02183/정답16/부분6/14호출, API0.
- [ ] Step 4: 코드 고정 후 합성 실험, gate 통과 시만 H02를 실행한다. Expected: 성공 또는 명시적 terminal 실패; 코드 불변, 상한 준수, 실패 미채점. 사전 기대 점수에 맞춰 변경하지 않는다.
- [ ] Step 5: 결과를 기록하고 전체 tests와 runtime_tests를 task-done 검증한다. Expected: 선택 의존성 기존 skip 외 모두 성공. 새 컨텍스트 전체 브랜치 리뷰 후 Important/Critical 단일 수정, feature push/정확한 CI를 확인한다.
