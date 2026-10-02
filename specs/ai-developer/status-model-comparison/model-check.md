# 모델·무료 조건·호환성 확인

확인일: 2026-10-02 KST. 공개 공식 문서만 조회했다. 인증 API 호출·계정 화면 확인은 하지 않았다.

## 선정

비교 후보는 **GLM 5.3 (`z-ai/glm-5.3`) 1개**다.
NVIDIA Build의 현재 표기에 Free Endpoint가 Available이고 API 예제는
`https://integrate.api.nvidia.com/v1`을 사용한다.
기준 DeepSeek V4.1 Flash의 공개 페이지도 무료 엔드포인트를 표시한다.
모델 크기나 일반 벤치마크를 AgentFit 성능 개선의 근거로 사용하지 않는다.

근거: [GLM Build](https://build.nvidia.com/z-ai/glm-5-3),
[DeepSeek Build](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash).

## 무료 사용 조건

- NVIDIA Developer Program FAQ는 회원의 API endpoint 프로토타이핑 접근을 무료로 안내한다.
- API Trial 약관 1.2·1.4는 내부 시험·평가 목적의 제한된 접근, 기간·횟수·크레딧 제한 가능성을 설명한다.
  무료 대상 표시는 무제한 사용이나 특정 계정의 현재 잔량을 보장하지 않는다.
- 파트너 유료 엔드포인트, 유료 구독·충전, 운영 배포는 이 계획의 대상이 아니다.
- 현재 계정의 무료 모델 접근권, 이번 8회와 입력/출력 크기를 감당할 잔량,
  초과 시 자동 과금·유료 전환 없이 거절되는 조건은 **미확인**이다.
  공개 문서의 402 응답 설명도 개별 계정의 과금 설정 확인을 대신하지 않는다.
- 기존 사용자 확인 기록은 만료되어 **사용 불가**다. 실행 직전 새 확인 시각·유효 기한·모델·endpoint·
  잔여 무료 범위·초과 처리의 근거를 비밀 값 없이 기록한다. 미확인 항목이 있으면 호출 0회로 종료한다.

근거: [NVIDIA FAQ](https://docs.api.nvidia.com/nim/docs/product),
[API Trial 약관](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf).

## 동일 스키마·문맥 호환성

| 항목 | 이번 확인 | 판정 |
|---|---|---|
| GLM 모델 ID·endpoint | 전용 API reference와 Build 예제 일치 | 문서 확인 |
| system/user 메시지 | Build 예제 제공, API는 messages 지원 | 문서 확인 |
| 전체 문맥 | GLM 공식 한도 1,048,576토큰. 기존 US 입력은 DeepSeek 기준 최대35,964 prompt tokens | 용량상 가능성이 높음. GLM 토큰화 및 실제 hosted 수용은 미검증 |
| temperature=0, max_tokens=8192, SSE | GLM API에 temperature 0~1, max_tokens>=1, stream 명시 | 인자 형식 문서 확인. 8192의 실제 처리 미검증 |
| response_format=json_schema, strict=true | GLM 전용 reference에 이 인자·strict·세부 schema keyword가 명시되지 않음 | 미확인, 미지원으로 단정하지도 않음 |
| chat_template_kwargs.thinking=false | 저장 US 요청의 옵션. GLM 전용 reference에는 명시되지 않음 | 미확인 |

근거: [GLM API 요청 규격](https://docs.api.nvidia.com/nim/reference/z-ai-glm-5-3-infer),
[GLM 모델 카드](https://build.nvidia.com/z-ai/glm-5-3/modelcard).
GLM 모델 카드는 reasoning_effort 및 clear_thinking도 설명하지만,
clear_thinking은 thinking=false와 같은 옵션이라고 간주할 수 없다. 이들을 임의로 추가·대체하지 않는다.

일반 [NIM structured generation 문서](https://docs.nvidia.com/nim/large-language-models/1.14.0/structured-generation.html)는
guided_json을 설명한다. 이는 해당 hosted GLM 엔드포인트에서 현재 response_format 계약을
지원한다는 증거가 아니므로 schema를 guided_json/json_object/tool calling으로 바꾸지 않는다.

**판정:** 공개 무료 후보 선정과 문맥 규모 확인은 완료했다. 계정 무료 범위와 정확한 요청 호환성은
아직 실행 가능 판정에 부족하다. 새 공식/계정 안내로 확인하거나, 무료 재확인 후 사용자가 승인한
첫 GLM 본 배치(총8회 안에 포함)에서 호환성을 점검한다. 옵션 거절·무시 의심 또는 추론 모드 동등성을
확인할 근거가 없으면 분류 성능 우열 판정은 보류한다. 이번 단계에서는 이 점검 호출도 실행하지 않는다.

temperature=0이어도 다른 모델의 토큰화·서빙·기본 샘플링 값은 같다고 보장할 수 없다.
현재 payload는 top_p/seed를 생략한다. 이를 모델별로 추가 튜닝하지 않으며,
비교 결과는 고정 요청 계약에서의 hosted 모델 차이로 해석한다.
