# 복구형 Solar 로컬 서비스 모드

## 목적

선택형 `RecoverableSolarAnalyzer`를 현재 요청별 격리 Worker와 FastAPI 경계에서 실제로 실행할 수 있게 한다. 기본 서비스의 분석 방식은 바꾸지 않는다. Spring의 확인·저장 계약이 준비되지 않았으므로 운영 기본 활성화는 금지한다.

## 계약

- 서비스 설정 `AGENTFIT_ANALYSIS_MODE`는 `default`(기본) 또는 `recoverable-solar`만 허용한다. 앱 생성 인자로도 같은 모드를 지정할 수 있다. 잘못된 값은 시작 시 실패한다.
- 복구 모드일 때만 내부 프로세스 요청에 `mode: recoverable-solar`를 전달한다. 기본 모드의 요청 형식은 그대로 둔다. 모드는 HTTP 클라이언트 헤더나 문서 내용으로 선택할 수 없다.
- Worker는 복구 모드에서 `RecoverableSolarAnalyzer`를 40초 분석 제한과 기존 `post_solar_inline`으로 실행한다. `complete`, `needs_confirmation`, `failed`를 반환한다. 기본 모드는 기존 `SolarAnalyzer`를 실행한다.
- 프로세스 경계는 정확한 결과 키와 안전 오류 코드를 확인한다. FastAPI는 기존 Profile·질문 검증을 다시 수행한다. 원문·키·원본 예외는 오류 응답에 포함되지 않는다.
- 요청 취소, 연결 종료, 60초 서비스 기한, 프로세스별 격리는 기존과 같다. 단일 로컬 실행만 검증하며 Spring 저장 경로는 연결하지 않는다.

## 수용 기준

1. 기본 모드 입력/출력은 변경되지 않고 미지원 모드는 거절된다.
2. 복구 모드의 `needs_confirmation`이 Worker→프로세스→FastAPI를 통과한다. 결과 검증이 실패하면 안전 오류로 거절된다.
3. 로컬 HTTP 호출은 가짜 Provider로 실행해 외부 문서 전송 없이 확인 질문을 관측한다.
4. 전체 AI 서비스 테스트와 프로세스 종료/기한 회귀 테스트가 통과한다.
