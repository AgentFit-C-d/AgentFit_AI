# DeepSeek 검토 추론 비교 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자가 승인한 직접 구현과 목표 내 자율 진행을 적용한다.

**Goal:** 동일 후보에서 DeepSeek thinking 설정의 검토 효과를 재현 가능한 안전한 보고서로 비교한다.

**Architecture:** 기존 snapshot 복원·검토·Profile 투영·채점 함수를 재사용하는 선택형 평가 모듈을 추가한다. 실제 전송 직전에 Boolean만 바꾼다. 로컬 실행 드라이버는 승인된 H02의 hash와 기존 정답을 고정한다.

**Tech Stack:** Python 3.13, unittest, 기존 NVIDIA streaming/nonstreaming transport.

**Spec:** specs/ai-developer/04-analysis-provider/deepseek-review-thinking/spec.md

## Global Constraints

- 기본 서비스와 공개 Profile 변경 없음. temperature=0/max_tokens=8192/timeout=600/batch20/reasoned_review=true/explicit-v1/재시도0.
- 합성 최대4호출, H02 최대14호출. 원문·인용·값·키·원시 응답·추론 텍스트 출력/저장 금지.
- 사전 검증 실패는 API0. 제공자/계약 실패는 정확도 미평가. 기존 16개·6개 정답 유지.
- feature/deepseek-review-thinking에 검증 후 push. 사용자 공유 환경과 main checkout 수정 없음.

## Review Focus

1. payload의 thinking 외 필드가 달라지거나 이전 arm이 다음 arm 입력을 오염시키면 비교가 무효다.
2. 스냅샷/정답/키 검증이 첫 요청보다 늦으면 승인되지 않은 전송이나 잘못된 점수가 생긴다.
3. 첫 arm 실패·중간 보고·callback이 제공자 재시도나 거짓 성공을 만들면 안 된다.
4. 예외·모델 문자열·정답 또는 private 값이 보고서에 유출되면 안 된다.
5. reasoning 텍스트 미존재, length 응답, 30개 초과 기능, 한 문서 비교를 품질 개선으로 과대 해석하면 안 된다.

### Task 1: 동일 후보 비교 도구와 한정 실험

**Files:**
- Create: ai_service/agentfit_ai/candidate_thinking_evaluation.py
- Test: ai_service/tests/test_candidate_thinking_evaluation.py
- Create: specs/ai-developer/04-analysis-provider/deepseek-review-thinking/validation.md
- Create: work/harness/deepseek-review-thinking/STATE.md
- Local ignored: E:/AgentFit/tmp/run-deepseek-thinking-h02-v1.py 및 안전한 결과 JSON

**Interfaces:**
- Consumes: restore_snapshot(case, snapshot), review_candidates_separately, finalize_candidate_analysis, score_profile, post_nvidia_streaming.
- Produces: evaluate_thinking_reviews(case, snapshot, key, *, expected_keep, transport=None, on_update=None) → enum/ID/count/hash-only dict. on_update는 복사된 중간 결과를 받는다.

- [x] Step 1: 입력 불변·동일 설정·실패 격리·호출 전 hash/gold 검증·출력 비밀 배제 회귀 테스트를 작성하고 import 실패를 확인한다.
- [x] Step 2: 최소 모듈을 구현한다. 기존 helper로 두 arm을 순차 실행하고 실패는 고정 코드만 기록한다. 정답과 원문은 callback에 전달하지 않는다.
- [x] Step 3: `python -m unittest discover -s tests -p test_candidate_thinking_evaluation.py -v`, 전체 tests와 runtime_tests를 실행한다. Expected: 모두 성공, 기존 선택 의존성 제외만 유지.
- [x] Step 4: 로컬 드라이버에서 소스·스냅샷·코드 hash와 최대 호출 수를 검증한다. 합성 probe가 통과할 때만 H02 false/true를 한 번 실행한다. 실패도 terminal 결과로 감사한다. 결과:3호출로 gate 실패, 최초H02 미실행.
- [x] Step 4a (실제 오류로 추가): 합성 true가 stop/58tokens/추론177자로 돌아왔지만 INVALID_RESPONSE다. 같은 합성 후보 요청에서 thinking=true를 고정하고 response_format 존재/부재만 바꾼 최대2호출을 별도 파일로 진단한다. 최종 content와 reasoning의 길이·JSON 여부·예상 키 일치 Boolean만 저장한다. 원본 probe와 H02 gate는 변경하지 않는다.
- [x] Step 4b: `structured_output=True` 선택 인자를 추가해 False에서는 양쪽 모두 response_format만 제거한다. schema-free에서도 불변 입력과 엄격 JSON 검증 유지 테스트를 RED→GREEN으로 완료한다. 일회성 callback 예외가 parser에서 흡수되는 재현 테스트도 RED→GREEN으로 수정한다. 전체/SDK 테스트 후 별도v2 합성4회 이내→통과 시H02 14회 이내. 전체 실험상한24, 각종 원본 결과 보존. 결과: v2합성4회 gate통과, H02 2회로 양조건 실패/미평가.
- [x] Step 4c: 실행 중인H02v2 terminal과 frozen code를 감사한 뒤, False 옵션의 system 메시지에 기존 schema 전체를 보존한다. `test_schema_free_pair_retains_exact_schema_in_system_prompt`로 기존 schema 객체와 prompt JSON의 완전 일치, user 메시지 불변, 두 thinking 조건 대칭을 RED→GREEN 검증한다. 출력 계약 검증은 완화하지 않는다. 실제 후속 API는 새 사전 계획 없이는 시작하지 않는다.
- [x] Step 5: 명세 판정 기준대로 validation.md/STATE.md를 작성하고 task-done 검증, 새 컨텍스트 전체 브랜치 리뷰, Important/Critical 단일 수정, commit/push를 완료한다. 제품2dcf721 push/CI통과. 리뷰0Critical/0Important/1Minor(request_bytes 진단 기준), 문서에 제한 기록.
