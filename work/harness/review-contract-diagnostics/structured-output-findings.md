# 구조화 응답 지원 조사 — 2026-09-30

## 확인한 사실

- [GLM-5.3 NVIDIA API](https://docs.api.nvidia.com/nim/reference/z-ai-glm-5-3-infer)는 OpenAI 호환 Chat Completions와 SSE를 설명한다. 읽은 요청 매개변수 문서에는 response_format/json_schema의 제약별 보장 범위가 명시되지 않았다. 문서의 생략만으로 미지원이라고 단정할 수 없다.
- [GLM-5.3 NVIDIA 모델 카드](https://build.nvidia.com/z-ai/glm-5-3/modelcard)는 reasoning_effort의 low/high/max, clear_thinking 설정과 vLLM/Dynamo 추론 환경을 설명한다. 현재 어댑터의 low·clear_thinking=True와 방향이 맞는다.
- [NIM LLM1.14 구조화 생성](https://docs.nvidia.com/nim/large-language-models/1.14.0/structured-generation.html)은 guided_json과 xgrammar를 설명하지만 self-hosted NIM 예제다. 이를 preview endpoint의 보장이나 교체해야 할 매개변수로 곧바로 적용하지 않는다.
- [Dynamo GLM-5.3/5.2 SGLang recipe](https://docs.nvidia.com/dynamo/dev/recipes/glm-5-2)는 구조화 decoding에서 enable_thinking=False를 요구한다고 설명한다. 반면 [Megatron Bridge의 GLM-5.3 템플릿 비교](https://docs.nvidia.com/nemo/megatron-bridge/nightly/models/glm/glm5-2.html)는 해당 템플릿이 enable_thinking=False를 따르지 않는다고 명시한다. 배포·템플릿 맥락이 다르므로 현재 preview 설정을 추측으로 변경하지 않는다.

## 코드에서 확인한 형식과 의미의 경계

현재 candidate_split_review.py의 JSON schema는 checkedCandidateIds/wrongCandidateIds의 ID enum과 길이, 반려 사유 행의 키와 reason enum을 전달한다. 그러나 아래 규칙은 서버 predicate에서 별도로 강제한다.

- checkedCandidateIds가 요청 순서와 정확히 일치해야 한다.
- wrongCandidateIds에 중복이 없어야 한다.
- rejectionReasons가 wrongCandidateIds의 모든 ID와 일대일로 연결돼야 한다.

따라서 응답이 JSON schema를 따르더라도 위 세 조건을 위반할 수 있다. 이는 파라미터 지원 문제와 독립된 코드상의 사실이다. 새 진단이 ORDER/DUPLICATE/REJECTION_REASONS_COUNT 등을 보고하면 구조화 생성 지원 변경만으로 해결된다고 가정해서는 안 된다.

## 판단과 다음 행동

- 제품 설정 변경0. 현재 H02(session56367) 분석 코드는 동결 유지.
- 실제 contract_issue가 나올 때까지 과거 실패 원인은 미확인이다. 정확한 원인을 확인한 후 요청 계약 또는 수정 방식의 변경을 SDD로 구체화한다.
- ID/사유의 중복 표현이 실패 원인으로 확인된다면 후보별 단일 판정 표현이 모순을 없애는지 검토할 수 있다. 이는 아직 구현 결정이나 효과 입증이 아니다.
- 의미 정확성은 구조화 형식과 별도 평가 대상이다. JSON 검증 성공을 사용자에게 자동 확정할 근거로 사용하지 않는다.

## 일회성 합성 probe

- 질문: GLM preview가 프롬프트와 충돌하는 JSON enum을 강제하는가? 같은 짧은 합성 메시지와 marker enum에 json_schema(strict=True), guided_json을 각각 한 번 요청한다. 추가 API는 최대2회이며 문서나 개인정보를 보내지 않는다.
- 드라이버/보고서: E:/AgentFit/tmp/probe-glm-structured-format-20260930.py 및 .json. session82995. 제품 파일을 수정하지 않는 spike다.
- 성공 한두 번으로 보편적 schema 보장을 주장하지 않는다. 위반 관측은 해당 설정·요청에서 강제되지 않은 사례로만 판정한다. 실패하면 오류 코드만 기록하며 이를 모델의 의미 판단 점수로 세지 않는다.
- H02와 같은 계정에서 별도 probe를 실행했으므로 이번 문서 지연은 순수한 이전 지연 비교로 사용하지 않는다. 문서의 호출 예산·payload·정답·동결 revision은 유지하고 두 실험의 호출 수를 분리한다.

### 결과

- session82995 종료exit0, 실제2호출. json_schema 91,816ms, guided_json 79,675ms. 둘 다 finish=stop, 파싱 성공, schema의 marker enum 충족, 상충하는 프롬프트 값은 반환하지 않았다. 응답 본문은 보고서에 남기지 않았다.
- 두 설정의 이 작은 사례에서는 스키마 제한이 관측됐다. 현재 방식이 항상 무시된다는 가설은 지지되지 않는다. 복합 배열 제약이나 의미 정확성, 모든 요청에서의 강제 보장을 입증하지는 않는다.
- 설정을 guided_json으로 바꿀 근거가 없어 현재 json_schema를 유지한다. 실제 검토 진단 결과로 어떤 관계 조건이 어긋났는지 먼저 판단한다.
- 재사용 조사: atomic_verdict.py는 후보 ID를 키로 두는 enum 판정 계약을 이미 구현한다. 다만 이는 추출 후보의 분류 계약이며 현재 검토의 지지/반려 사유와 의미가 다르다. candidate_review_replay.py는 해시·ID·위치·라벨을 검증한 snapshot을 재사용할 수 있지만 새 평가 드라이버는 classification_refs를 기록하지 않는다. 기존 함수 존재만으로 이번 실측을 재생할 수 있다고 주장하지 않는다.
