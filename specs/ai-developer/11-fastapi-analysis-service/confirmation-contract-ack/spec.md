# 복구형 분석 응답 계약 수락

## 문제

현재 Spring 공개 분석 API는 `draft`와 `attempt`만 정의하고, `needs_confirmation`의 `fieldStates`·`questions`를 저장·재조회하는 계약은 없다. FastAPI 복구 모드를 설정만으로 활성화하면 Spring이 HTTP 200을 일반 초안 성공으로 오해할 수 있다.

## 내부 계약

- `AGENTFIT_ANALYSIS_MODE=recoverable-solar`에서 호출자는 정확히 한 개의 `X-AgentFit-Analysis-Contract: confirmation-v1` 헤더를 보내야 한다.
- 헤더가 없거나 중복되거나 값이 다르면 인증 이후, body를 읽거나 분석 슬롯을 확보하기 전에 HTTP 428 `{ "error": "CONFIRMATION_CONTRACT_REQUIRED" }`로 거절한다.
- `default` 모드는 헤더 없이 기존대로 동작한다. 헤더만으로 복구 모드를 켤 수 없다.
- 이 수락 신호는 Spring의 실제 저장·재조회·사용자 확인 구현을 증명하지 않는다. 운영 활성화 전 Full Stack A가 공개 API와 DB·UI 계약을 구현하고 검증해야 한다.

## 수용 기준

1. 복구 모드에서 헤더 누락·오타·중복은 분석 전 428이다.
2. 정확한 헤더를 보낸 복구 모드 요청은 기존 `needs_confirmation` 결과를 전달한다.
3. 기본 모드의 헤더 없는 요청과 요청 취소·기한 테스트는 유지된다.
