# 동일 후보 검토 비교 검증

## 코드 검증

- 검토 모델 옵션과 최종 변환 함수의 부재를 RED로 확인한 뒤 구현했다. 기존 기본 Solar 경로의 회귀와 함께 통과했다.
- 같은 원문·후보·분류를 두 모델에 전달하고 첫 모델의 실패/입력 변경이 다음 모델에 영향을 주지 않음을 검증했다. 추출·분류는 각각1회다.
- NVIDIA 반환 모델을 그대로 검증한다. 다른 모델 응답과 length를 Solar 복구 경로로 통과시키지 않는다. 키는 제공자별로 분리한다.
- 두 키 중 하나가 문서에 들어 있으면 API 전에 차단한다. 공통 실패도 두 모델의 실패로 남긴다.
- 합성 사례에서 이름2개는 `multiple_scalar_values`로 남고, 한 모델이 잘못된 기술 후보를 제외했을 때만 backend 미정 채점이 바뀐다. 값·원문·키는 집계에 없다.
- 새12건과 관련 기존15건, 총27건 통과. 실제 CLI 함수는 테스트 manifest와 비밀이 아닌 fixture 키를 읽고 안전한 최종 JSON을 생성했다.
- 전체848건 실행(6건 건너뜀,842건 통과), 종료 코드0을 확인했다. diff 공백 검사도 통과했다. 실제 문서 비교·독립 리뷰·CI는 아직 진행 전이다. 모델 품질 개선을 주장하지 않는다.

## 모델 설정 근거

기존 NVIDIA adapter를 재사용한다. 공식 모델 페이지에서 모델 ID와 endpoint 예시를 확인했다: [DeepSeek V4.1 Flash](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash), [GLM5.3](https://build.nvidia.com/z-ai/glm-5-3), [Kimi K3](https://build.nvidia.com/moonshotai/kimi-k3). JSON 계약의 실제 호환성은 코드 테스트와 별도의 실호출 결과로 판정한다. Solar medium과 DeepSeek thinking=false 등 설정 차이는 결과의 review_settings에 기록한다.
