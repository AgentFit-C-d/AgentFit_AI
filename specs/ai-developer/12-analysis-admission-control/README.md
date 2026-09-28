# 분석 요청 수용 제한

FastAPI 프로세스마다 기본 2개의 분석 요청만 동시에 수용한다. 인증·헤더 검사를 통과한 요청이 슬롯을 얻으면 body 읽기부터 분석 응답 완성까지 슬롯을 사용한다. 포화 시 `503 SERVICE_BUSY`와 `Retry-After: 1`을 반환한다.

환경 변수 `AGENTFIT_MAX_INFLIGHT_ANALYSES`는 1~8, `AGENTFIT_UPLOAD_TIMEOUT_SECONDS`는 1~30의 정수로 설정한다. 후자의 기본값은 10초이며 body 업로드 전체가 이를 넘으면 `408 DOCUMENT_UPLOAD_TIMEOUT`을 반환한다. 잘못된 값은 서버 시작을 실패시킨다.

이 제한은 프로세스마다 적용된다. 운영 시 Uvicorn worker 수와 각 프로세스 설정을 함께 계산해야 한다. Spring Boot의 503 재시도 정책과 전체 요청 취소 계약은 별도 합의가 필요하다.
