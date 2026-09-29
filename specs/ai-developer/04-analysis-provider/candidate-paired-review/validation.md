# 동일 후보 검토 비교 검증

## 코드 검증

- 검토 모델 옵션과 최종 변환 함수의 부재를 RED로 확인한 뒤 구현했다. 기존 기본 Solar 경로의 회귀와 함께 통과했다.
- 같은 원문·후보·분류를 두 모델에 전달하고 첫 모델의 실패/입력 변경이 다음 모델에 영향을 주지 않음을 검증했다. 추출·분류는 각각1회다.
- NVIDIA 반환 모델을 그대로 검증한다. 다른 모델 응답과 length를 Solar 복구 경로로 통과시키지 않는다. 키는 제공자별로 분리한다.
- 두 키 중 하나가 문서에 들어 있으면 API 전에 차단한다. 공통 실패도 두 모델의 실패로 남긴다.
- 합성 사례에서 이름2개는 `multiple_scalar_values`로 남고, 한 모델이 잘못된 기술 후보를 제외했을 때만 backend 미정 채점이 바뀐다. 값·원문·키는 집계에 없다.
- 새12건과 관련 기존15건, 총27건 통과. 실제 CLI 함수는 테스트 manifest와 비밀이 아닌 fixture 키를 읽고 안전한 최종 JSON을 생성했다.
- 전체848건 실행(6건 건너뜀,842건 통과), 종료 코드0을 확인했다. diff 공백 검사도 통과했다.
- 코드5c82f5c를 feature/candidate-paired-review에 push했고 Linux CI36625914141 성공을 확인했다.
- 독립 리뷰에서 P0/P1/P2 수정 권고 없음. 리뷰어는 관련11개 테스트를 추가 실행해 통과했다. 실제 모델 품질·라이브 JSON 호환성·비공개 골드 타당성은 코드 리뷰로 판단하지 않았으며 아래 실측에서 확인한다. Linux CI는 메인 작업에서 직접 조회했다.
- 경미한 미반영 사항: --env-file은 argparse에서 required로 강제하지 않고 기존 키 로더가 미지정을 거부한다. 이번 실행은 명시적 경로를 전달한다. 사전 옵션 검사로 옮기는 정리는 보류했다.
- 모델 품질 개선을 주장하지 않는다.

## 모델 설정 근거

기존 NVIDIA adapter를 재사용한다. 공식 모델 페이지에서 모델 ID와 endpoint 예시를 확인했다: [DeepSeek V4.1 Flash](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash), [GLM5.3](https://build.nvidia.com/z-ai/glm-5-3), [Kimi K3](https://build.nvidia.com/moonshotai/kimi-k3). JSON 계약의 실제 호환성은 코드 테스트와 별도의 실호출 결과로 판정한다. Solar medium과 DeepSeek thinking=false 등 설정 차이는 결과의 review_settings에 기록한다.

## 실제 H02 실행 — 진행 중

- 실행 코드5c82f5c. 기존 승인 manifest의 LF 정규화 SHA256은 a69837761609613a5252e6014f85d996681ef54c2c0938a68fdb9208deb0db95.
- PID5468, 시작 UTC2026-09-29T20:25:05.3135979Z, 시작 셸 세션60976. 중복 실행 전에 PID/시작 시간과 결과의 state를 함께 확인한다.
- 결과: E:/AgentFit/tmp/candidate-paired-review-h02-20260930-v1.json
- 프로세스 기록: 같은 basename의 -process.json. stdout/stderr는 .stdout.log/.stderr.log. 원문·키·원본 응답은 저장하지 않는다. 모두 Git 제외 로컬 파일이다.
- 공통 추출·분류가 끝나면 state=running 중간 집계가 생성되고, 각 모델 종료 후 갱신된다. **파일 존재만으로 실행 종료를 판단하지 않는다.** state=finished와 실제 프로세스/셸 종료를 확인한다.
- Solar와 DeepSeek가 동일 후보를 받는 실제 비교는 아직 끝나지 않았다. 기존4/6 H02는 별도 실행이므로 이번 두 모델의 공통 기준으로 사용하지 않는다.
