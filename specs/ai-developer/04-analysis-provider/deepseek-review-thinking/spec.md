# DeepSeek 검토 추론 비교

## 목적과 근거

실사용 목표의 의미 검토 오류를 줄일 후보 설정을 평가한다. 이전 H02 고정 183개 후보에서 DeepSeek의 사전 지정 16개 유지/제외 판단은 13/16이었다. GLM은 15/16이었지만 실제 통합 평가에서 제공자 오류가 반복됐다. 같은 추출을 다시 실행하면 후보 차이가 섞이므로 저장된 ID·위치·분류를 복원한다.

이번 작업은 선택형 평가 도구다. 기본 서비스, 공개 Profile, 추출·분류·검토 프롬프트는 변경하지 않는다. 전체 실사용 완료 조건은 별도로 유지한다.

## 계약

- 모델은 `deepseek-ai/deepseek-v4.1-flash`, 순서는 thinking=false → true. 실제 전송 직전에 이 Boolean만 변경하고 입력 객체는 수정하지 않는다.
- 양쪽 모두 temperature=0, max_tokens=8192, timeout=600, reasoned_review=true, field_semantics=explicit-v1, batch=20, 자동 재시도=0. 실제 문서 비교는 양쪽 모두 기존 streaming 전송을 쓴다.
- 후보 검토 입력은 두 조건에서 동일하다. 후속 coverage의 confirmedValues는 각 조건의 유지/제외 판단을 반영하므로 달라질 수 있다. 이는 설정 변경의 후속 효과이며 전체 요청 byte가 같다는 뜻은 아니다.
- snapshot·원문·redacted hash, ID·위치·분류는 기존 restore_snapshot으로 검증한다. 키와 문서/ID 충돌 및 평가 정답 오류는 API 호출 전에 차단한다.
- 호출마다 순서·조건·경과 시간·고정 오류 코드만 보고한다. 원문·값·인용·API 키·원시 응답·추론 텍스트는 기록/출력하지 않는다.
- 각 조건에서 후보 검토와 전체 원문 누락 검토를 모두 완료한 경우에만 16개 사전 정답과 6개 기존 부분 정답을 집계한다. 중도 실패는 미평가이며 0점으로 바꾸지 않는다. 한 조건의 실패가 다른 조건의 시도를 막지는 않는다.
- 사용자 문서 비교 전에 합성 문서의 PostgreSQL 확정 / MongoDB 검토안 / Redis 미사용 3개를 같은 API로 검사한다. true 조건의 구조 검증·3/3 판단·비어 있지 않은 reasoning 응답 존재 여부를 확인한다. 추론 텍스트는 즉시 폐기하고 길이만 계산한다. 이 확인이 실패하면 H02 호출은 실행하지 않는다.
- 합성 검증은 최대4호출(nonstreaming), H02는 최대14호출(streaming), 추가 반복/자동 튜닝은 없다. 합성에서 전송 방식이 다른 것은 옵션 지원 확인을 위한 것이며 성능 비교로 사용하지 않는다.
- 최초 합성 true에서 stop/58tokens/추론177자와 INVALID_RESPONSE가 관측돼 원인 확인용 합성2호출을 별도로 추가한다. thinking=true와 모든 나머지 값은 고정하고 response_format 유무만 비교한다. 길이·JSON/예상 키 일치 Boolean으로 판단하며 추론 텍스트는 사용하지 않는다. 이 진단이 원래 실패를 대체하거나 H02 gate를 통과시키지는 않는다. 전체 상한20회.
- H02 기존 183개 후보와 source/redacted hash를 고정한다. 정답 ID: 유지 C067/C069/C077/C080/C082/C087/C099/C101/C109/C156/C165, 제외 C058/C059/C064/C153/C154.
- 기존 추출·분류·골드는 이미 튜닝에 사용됐다. 독립 평가나 전체 정확도로 보고하지 않는다. 이번 경로는 대표 기능 30개 요약을 실행하지 않으므로 Profile 기능 상한 실패를 모델 오판과 구분한다.

## 판정

true 조건이 유효하게 완주하고, 16개 판단이 같은 실행의 false 조건보다 개선되며, 6개 부분 정답이 악화되지 않아야 후속 통합 실험 후보로 채택한다. 한 번의 비교만으로 기본 모델을 변경하지 않는다. 동률·회귀·응답 실패는 채택 근거 부족으로 기록한다.

## 관측된 형식 호환성에 따른 후속 비교

합성 진단에서 thinking=true+json_schema는 content가 문자열이 아니며 reasoning에 예상 키/정답을 가진177자 JSON이 들어갔다. json_schema를 제거한 동일 요청은 content177자 JSON, reasoning725자, 기존 파서 수락이었다. 원인 위치가 응답 채널 배치임을 확인했으므로 아래 제한 실험을 추가한다.

- `structured_output: bool = True`를 평가 함수에 추가한다. False일 때 양쪽 모두 전송 payload의 response_format만 제거하고 기존 서버 JSON/필드/후보 ID/근거 검증은 유지한다. True 기본값 및 서비스 코드에는 영향이 없다.
- 최초 실험은 실패로 보존하고 그 H02는 실행하지 않는다. 별도 v2 파일에서 schema-free 합성 최대4호출로 다시 gate를 확인한 뒤 같은 설정의 H02 최대14호출을 시행한다. 원래3~4호출+진단2+새합성4+H0214=전체상한24회. 새 골드나 프롬프트 변경은 없다.
- 비교의 분모·판정은 위와 동일하다. schema-free false/true 사이의 효과만 비교하고 최초 schema-on 결과와 직접 정확도 차이를 주장하지 않는다. 추론 필드의 JSON을 최종 응답으로 사용하지 않는다.
- 일회성 progress observer 실패도 이후 API 호출을 중지해야 한다. 제공자 parser가 예외를 바꿔도 원래 observer 오류 상태를 보존한다.

## 공식 근거와 미확인

- [NVIDIA 모델 설명](https://docs.api.nvidia.com/nim/reference/nvidia-deepseek-v4_1-flash): thinking 및 1~100 reasoning effort를 설명한다.
- [vLLM 공식 모델 레시피](https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4.1-Flash.yaml): chat_template_kwargs.thinking Boolean을 설명한다.
- NVIDIA 호스팅 엔드포인트가 해당 옵션을 실제 적용하는지는 문서만으로 확정하지 않는다. 합성 호출로 응답 메타데이터를 확인한다. 숫자 effort나 temperature까지 동시에 바꾸지 않는다.
