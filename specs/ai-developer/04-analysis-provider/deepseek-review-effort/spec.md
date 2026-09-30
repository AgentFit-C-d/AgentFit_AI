# DeepSeek 검토 추론량 명시 실험

## 목적과 근거

이전 H02 비교는 off가 출력 행 계약 오류, on이 8,192토큰 length로 모두 미평가였다. 최종 수정은 JSON Schema를 system prompt에 보존하지만 실제 API로 아직 검증하지 않았다. 이를 유지한 채 off와 on+숫자 추론량25를 비교한다. 서비스 준비도나 전체 정확도를 작은 실험 성공으로 대신하지 않는다.

공식 vLLM [모델 설정](https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4.1-Flash.yaml)은 chat_template_kwargs.reasoning_effort 정수1~100을 설명한다. NVIDIA 호스팅의 내부 적용은 미확인이다. 25는 요청한 설정이며 추론량이 정확히 절반이 된다는 뜻이 아니다.

## 계약

- 기존 evaluate_thinking_reviews에 thinking_effort: int | None = None을 추가한다. exact int 1~100 또는 None만 허용하고 잘못된 값은 API 호출 전에 거부한다. bool도 거부한다.
- True arm에만 chat_template_kwargs.reasoning_effort를 넣는다. False arm과 None 기본 동작은 그대로다. settings 및 각 arm에는 요청한 추론량을 기록하며 백엔드 적용을 보증하지 않는다.
- 두 arm 모두 structured_output=False로 기존 schema 전체를 system prompt에 전달한다. 공개 Profile, 기본 분석기, 서버 JSON·ID·근거·의미 계약 검증은 유지한다.
- DeepSeek V4.1 Flash, temperature0, max_tokens8192, timeout600, batch20, reasoned_review=True, explicit-v1, 재시도0을 고정한다.

## 검증·실험

1. 새 인자의 범위·타입·None 호환·arm별 요청 차이·메타데이터를 단위 검증한다.
2. 서로 다른 기능20개를 확정7/검토7/부정6으로 만든 합성 문서에 동일한 confirmed 초기 후보를 주고 정답을 사전 고정한다. 양쪽20/20, 후보+coverage 계약 통과, on의 reasoning 메타데이터 존재가 실제 H02 전송 gate다. 최대4호출.
3. 통과한 경우만 기존 H02의 고정183후보·16개 판단 정답·6개 부분 정답으로 최대14호출을 실행한다. 추출·gold 변경은 하지 않는다. 총상한18호출, 자동 재시도 없음.
4. 두 조건이 유효한 경우만 같은 실행의 의미 판단 개선을 비교한다. 한 조건만 성공하면 설정 가용성의 증거이며 짝 비교 정확도 개선은 미확인이다. 실패한 조건은 정확도 미평가다.

## 개인정보·재현성

기존 개인정보 제거 H02 전송 승인을 적용한다. private 원문·발췌·값·원본 경로·키·원시 응답·추론 텍스트는 출력/저장하지 않는다. 보고서는 ID/enum/count/hash 및 근거 위치만 담는다. 코드·드라이버·helper·snapshot hash, 설정, 호출 수, terminal 상태를 기록한다. 기존 결과를 덮어쓰지 않는다. request_bytes는 변환 전 parser 크기이며 wire 크기로 해석하지 않는다.

## 완료 기준

회귀/전체/실제 SDK 검증, 한정 실험 terminal 감사, 결과 기록, 전체 브랜치 리뷰와 feature push. 실서비스 채택·배포·전체 목표 완료는 별도다.
