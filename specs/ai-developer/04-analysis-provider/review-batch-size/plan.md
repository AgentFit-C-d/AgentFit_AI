# 후보 검토 묶음 크기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 직접 구현 방식과 목표 내 자율 권한을 유지한다.

**Goal:** 한 번에 검토하는 후보 수만 제어하고 실제 오류 변화 여부를 측정한다.
**Architecture:** 기존 분할 루프와 평가 한도에 기본20인 keyword 옵션을 전달한다. 판단·정규화·실패·투영 계약은 유지한다.
**Tech Stack:** Python3.13,unittest,기존NVIDIA streaming.
**Spec:** specs/ai-developer/04-analysis-provider/review-batch-size/spec.md

## Global Constraints

- feature/review-batch-size,직접순차구현,기본HTTP/공개Profile불변.
- candidate_batch_size는exact int1..20,default20. 원문/후보/규칙/정답을수정하지않는다.
- 실제H02는batch10,confirmed109,최대12호출·retry0·전체유효시만채점. 원문/응답/추론/키미저장.

## Review Focus

1. 기본20 요청 호환과 기존 Solar adaptive 복구가 유지되는가.
2. 부분 마지막 묶음·비확정 후보·빈 목록에서 순서/범위/중복/coverage 조건이 맞는가.
3. 중간 실패·JSON정규화·observer 실패가 호출 한도를 우회하거나 부분 결과를 채점하지 않는가.
4. 평가의 실제 설정·계획 호출 수·실행기의12한도와 원문/후보/첫요청 비교가 일치하는가.
5. 과거 baseline과 단일새실행 차이를 인과·일반화·실사용 완료로 과장하지 않는가.

### Task 1: 분할 옵션·회귀·동일 문서 비교

**Files:**
- Modify: ai_service/agentfit_ai/candidate_split_review.py
- Modify: ai_service/agentfit_ai/candidate_thinking_evaluation.py
- Create: ai_service/tests/test_review_batch_size.py
- Create: specs/ai-developer/04-analysis-provider/review-batch-size/validation.md
- Create: work/harness/review-batch-size/STATE.md
- Local ignored: E:/AgentFit/tmp/run-review-batch10-h02-v1.py,감사기,안전한결과

**Interfaces:**
- Consumes: review_candidates_separately·evaluate_thinking_reviews와기존frozen H02 helper/정규화/투영.
- Produces: 두함수의candidate_batch_size=20 keyword;분할과호출한도에동일값적용.

- [x] Step 1: 기본20명시/생략요청동일,23confirmed+tentative에서10/10/3+coverage,1/20경계,무효값,중간실패,빈후보,adaptive10→5+5,평가양arm분할/한도/메타데이터테스트를작성한다.
- [x] Step 2: `python -m unittest discover -s tests -p test_review_batch_size.py -v`로RED확인. Expected:새옵션부재실패.
- [x] Step 3: 두함수에exact int검증·옵션전달·루프와ceil한도/메타데이터를최소수정하고focused테스트를실행한다. Expected:새테스트와기존split/thinking회귀통과.
- [x] Step 4: 전체tests/runtime_tests 및API0실행기preflight를실행한다. Expected:기존5skip외통과,SDK4/4,기본20첫요청기존hash동일,10요청차이는batch의존부분뿐,모의12호출로109후보누락/중복없음. 제품commit.
- [x] Step 5: 최대12call실제H02 1회→종료감사→유효시16/6와오제외/오유지채점. Expected:코드/hash불변·상한준수·미유효결과미채점.
- [ ] Step 6: 문서/task-done/fresh 전체리뷰,필요시Critical/Important단일RED→GREEN수정,featurepush/CI. Expected:증거·미확인·다음행동을분리한다.

#### Step 6 검증 보완 (2026-09-30)

마감 전체 테스트에서 로컬 HTTP 테스트 5개가 간헐적으로 부모 프로세스 제한 시간에 걸렸다. 이후 계측 전체 실행은 1043개 중 1038통과/5skip이었으나, 느린 응답 테스트 4개가 서버 요청 도착 전에 종료되는 검증 빈틈을 확인했다. 이전 5실패의 환경 원인은 확정하지 않는다.

- 실제 응답 전송을 시작했음을 Event로 검증하는 assertion을 먼저 추가하고 RED를 확인한다.
- 로컬 프로토콜 오류 검증의 호출 예산은 10초, 실제 느린 응답 검증은 5초로 분리한다. 느린 응답은 해당 예산보다 길게 지속하고 6.5초 안의 종료와 전송 시작을 함께 확인한다.
- 제품 timeout/환경 설정/재시도는 변경하지 않는다. 기존 NVIDIA 요청 제한 전달 검증을 유지하고 Solar도 짧은 요청 제한 전달을 명시적으로 검증한다.
- 두 transport 파일과 전체/SDK 검증을 실행한다. 이는 간헐 실패 원인 해결을 주장하는 변경이 아니라, 실제 in-flight 중단 검증을 복원하는 테스트 보완이다.
