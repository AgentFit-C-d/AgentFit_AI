# DeepSeek V4.1 Flash 격리 비교 명세

## 목적
Solar Pro4의 고정 후보 통합 판정에서 남은 누락·오확정·근거 오류를 NVIDIA 제공 DeepSeek V4.1 Flash가 줄이는지 측정한다. 이 실험은 모델 성능 근거를 얻기 위한 것이며 기본 분석기와 공개 Profile을 변경하지 않는다.

## 입력과 계약
- 기존 `candidate-occurrence-expansion/evaluation-cases.json` 27건과 `atomic-candidate-verdict/counterexamples.json` 6건을 해시 검증해 그대로 쓴다. 원문 후보와 정답은 바꾸지 않는다.
- NVIDIA로 보내는 것은 이미 작성된 합성 자료의 문서와 후보뿐이다. 정답과 허용 근거는 보내지 않는다. 실제 문서와 예약 공개 문서는 사용하지 않는다.
- `ATOMIC_PROMPT`, `atomic_schema`, `candidate_views(..., focus=True)`, 서버의 `classify_atomic`·`score_profile`·근거 채점을 재사용한다.
- 요청 모델은 `deepseek-ai/deepseek-v4.1-flash`, 엔드포인트는 `https://integrate.api.nvidia.com/v1/chat/completions`, 키는 로컬 `NVIDIA_API_KEY`다.
- 합성 사전 점검에서 기본 추론 모드가 답변 없이 추론 토큰만 생성했다. `chat_template_kwargs: {thinking: false}`와 기존 strict JSON schema를 함께 적용한 요청은 유효한 JSON을 반환했다. 평가 설정에 이를 고정한다.
- 응답은 원본을 보관하지 않고, Solar와 같은 서버 검증을 통과해야 Profile 점수에 반영한다. 오류는 안전한 코드·토큰·지연만 기록한다.

## 비교·중단 기준
- 33건을 1회씩 실행해 기존 Solar atomic 33건 결과와 정답·오확정·서버 검증 실패·중앙값/p95 응답 시간을 비교한다. 기존 결과가 다른 시점의 호출이므로 시간 및 작은 차이는 잠정적이다.
- 오류나 결측을 성공으로 보지 않는다. 실패가 반복되거나 p95가 40초 호출 한도에 가까우면 기본값 승격을 검토하지 않는다.
- 실사용 준비 판정은 별도의 독립 실제 문서와 사용자 수정 부담 평가가 필요하다.

## 보안·호환성
- 키, 원본 모델 응답, reasoning, 실제 문서를 산출물에 기록하지 않는다.
- 서비스 기본 모델·API·요청 횟수/시간 예산은 변경하지 않는다.
