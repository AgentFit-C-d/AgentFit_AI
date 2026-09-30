# 검토 응답 진단 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 직접 구현 및 목표내자율권한을 적용한다.

**Goal:** 민감한 응답을 저장하지 않고 실제 형식실패 원인을 구분한다.
**Architecture:** 독립 순수 진단함수와 선택형 평가의 관측옵션. 응답채택파서와검증은그대로다.
**Tech Stack:** Python3.13,unittest,기존 NVIDIA streaming.
**Spec:** specs/ai-developer/04-analysis-provider/review-response-diagnostics/spec.md

## Global Constraints

- feature/review-response-diagnostics. 기본서비스/공개Profile/공유환경변경없음.
- raw·내용·키이름·값·추론·예외메시지출력금지. 고정enum/count/Boolean/null만기록.
- H02첫confirmed20개만각형식1회,최대2호출,재시도0. 고정gold/source/snapshot 유지.
- 형식진단을전체유효성/의미정확도/서비스준비도로과장하지않는다.

## Review Focus

1. 비정상 JSON/중복키/깊이초과/큰응답/비bytes가 진단에서 예외나 private 문자열을 유출하지 않는가.
2. 진단의 fence 관측이 서버의 응답 채택을 완화하거나 기본 요청을 바꾸지 않는가.
3. 임의의 응답 키·값·refusal·예외·추론은 enum/개수만 남고 callback에도 노출되지 않는가.
4. 실제 두 요청은 guided decoding 외에 동일하며 streaming·고정첫20개·2호출상한을 지키는가.
5. 한 묶음의 형식 결과를 전체 H02나 의미 정확도 개선으로 오해하지 않도록 보고하는가.

### Task 1: 순수 진단·선택 관측·고정 형식 실험

**Files:**
- Create: ai_service/agentfit_ai/review_response_diagnostics.py
- Modify: ai_service/agentfit_ai/candidate_thinking_evaluation.py
- Test: ai_service/tests/test_review_response_diagnostics.py
- Test: ai_service/tests/test_candidate_thinking_evaluation.py
- Create: specs/ai-developer/04-analysis-provider/review-response-diagnostics/validation.md
- Create: work/harness/review-response-diagnostics/STATE.md
- Local ignored: E:/AgentFit/tmp/run-review-format-h02-v1.py 및 safe결과JSON

**Interfaces:**
- Consumes: Solar의 MAX_RESPONSE_BYTES/_json, 기존 evaluate_thinking_reviews의 sender와 callback, 고정 H02 helper.
- Produces: describe_review_response(raw, expected_keys)→safe형태 dict, capture_response_shape=False 선택 인자.

- [ ] Step 1: 순수함수 실패분류·fence·키불일치·경계·privacy 테스트와 옵션기본호환·False/True형식실패유지·옵션bool검증 테스트를 먼저 작성하고 RED를 확인한다.
- [ ] Step 2: 최소구현 후 focused unittest를 실행한다. Expected: 모든새테스트와기존13테스트통과;변조된응답은여전히미평가.
- [ ] Step 3: 코드고정,전체tests/runtime_tests 검증,로컬드라이버preflight. Expected: 기존5skip외통과,고정첫20/형식2/최대2호출,API0.
- [ ] Step 4: streaming으로두형식각1호출실행. Expected: terminal성공또는고정실패,원문출력0,실행기·코드·문서hash불변,결과의문법/키/fence유형을확정가능한범위에서만판정.
- [ ] Step 5: 결과기록·task-done·독립전체브랜치리뷰·필요한Critical/Important단일수정·featurepush/CI. Expected:검증근거와미확인이분리됨,기본서비스미변경.
