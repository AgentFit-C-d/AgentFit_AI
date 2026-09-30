# JSON 코드 블록 정규화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 직접구현과목표내자율권한을적용한다.

**Goal:** 관측된포장오류를결정적으로처리하고전체H02의의미채점을재개한다.
**Architecture:** 기존안전한형태진단을조건으로하는순수bytes정규화함수와선택형평가옵션. 파서/의미검증은그대로다.
**Tech Stack:** Python3.13,unittest,기존NVIDIAstreaming.
**Spec:** specs/ai-developer/04-analysis-provider/review-json-fence-normalization/spec.md

## Global Constraints

- feature/review-json-fence-normalization,기본서비스·공개Profile변경없음.
- 단일완전fence만처리,partial복구/값수정없음. length/refusal/키/모델/ID/민감정보검증을우회하지않음.
- H02고정후보/정답,첫요청hash동일,최대7호출·재시도0,원문/응답/추론미저장.
- 전체완주시에만채점하고,한문서결과를실사용완료로대체하지않음.

## Review Focus

1. 여러블록/앞뒤설명/부분JSON/중복키/잘못된최상위키를정규화하여검증을우회하지않는가.
2. content외envelope·민감정보·모델·종료이유·ID/사유검증과기본요청호환을보존하는가.
3. 입력/출력한도·재인코딩실패·예외문구·진단callback에대한안전성이유지되는가.
4. 첫실제요청hash·고정109대상·7호출상한·실패미채점·변환전진단이실행기와결과에일치하는가.
5. 단일H02실행의완주/16개부분판단을의미품질·일반화·서비스운영증거로과장하지않는가.

### Task 1: 정규화 함수·선택 옵션·전체 검토

**Files:**
- Create: ai_service/agentfit_ai/review_json_normalization.py
- Modify: ai_service/agentfit_ai/review_response_diagnostics.py
- Modify: ai_service/agentfit_ai/candidate_thinking_evaluation.py
- Test: ai_service/tests/test_review_json_normalization.py
- Test: ai_service/tests/test_candidate_thinking_evaluation.py
- Create: specs/ai-developer/04-analysis-provider/review-json-fence-normalization/validation.md
- Create: work/harness/review-json-fence-normalization/STATE.md
- Local ignored: E:/AgentFit/tmp/run-normalized-review-h02-v1.py 및safe결과

**Interfaces:**
- Consumes: describe_review_response·공통fence규칙·기존파서/검토/투영/정답helper.
- Produces: normalize_review_json_fence(raw,expected_keys)→(raw_or_normalized_bytes,bool),normalize_json_fences=False옵션.

- [ ] Step 1: 정상bytes불변·단일fence내용보존·모든거부경계·재인코딩/한도·후속민감정보/모델/ID검증·옵션bool테스트를작성하고RED를확인한다.
- [ ] Step 2: 최소구현,focused검증. Expected:기존진단/평가회귀및새테스트통과,진단은변환전·raw/비밀유출없음.
- [ ] Step 3: 전체tests/runtime_tests,첫요청기존hash동일·109대상/최대7 preflight를확인한다. Expected:기존5skip외성공,API0. 제품commit으로고정한다.
- [ ] Step 4: streaming전체H02를1회실행한다. Expected:terminal성공또는고정실패,코드/hash불변·상한준수·성공시에만16/6채점. 결과에맞춰정답수정없음.
- [ ] Step 5: 결과문서·task-done·독립전체리뷰·필요시Critical/Important단일수정·featurepush/CI. Expected:실제근거와미확인범위를분리.
