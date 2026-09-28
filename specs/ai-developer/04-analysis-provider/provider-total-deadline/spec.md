# Solar HTTP 호출 총 기한

상태: 운영 안정화 기능.

## 문제

현재 `post_solar`는 `urllib`의 socket timeout으로 응답 전체를 `read()`한다. 응답 bytes가 조금씩 들어오면 매번 socket timeout 전에 진전하므로 호출 전체가 전달받은 `timeout`보다 오래 지속될 수 있다. 분석기의 40~60초 기한 검사도 이 전송 호출을 중단하지 못한다.

## 요구사항

- `post_solar(payload, api_key, timeout)`의 `timeout`을 **연결 시작부터 응답 body 완료까지** 단일 wall-clock 기한으로 취급한다. 헤더와 chunk 경계가 느리게 전송되어도 같은 기한을 적용한다.
- 응답 body는 기존 `MAX_RESPONSE_BYTES` 제한을 유지하고, 초과 시 즉시 `RESPONSE_TOO_LARGE`로 실패한다.
- 느린 스트리밍 응답은 기한에 `PROVIDER_TIMEOUT`으로 중단하고 연결을 닫는다. `Content-Length`/chunked 응답의 조기 종료는 `PROVIDER_NETWORK`로 처리한다. 키·body·예외 원문을 오류로 노출하지 않는다.
- DNS·TLS·헤더·본문 지연 모두 부모 프로세스의 전체 기한에 포함한다. 키는 자식의 명령줄 인자나 환경 변수에 넣지 않는다.
- HTTP status·network 오류 매핑과 외부 분석기 계약은 유지한다.
- 실제 로컬 HTTP 서버의 느린 헤더·body, 정상·잘린 응답으로 동작을 검증한다. Provider 외부 호출은 필요 없다.

## 범위 밖

FastAPI 요청 전체의 취소·동시성 제한과 PDF Worker 메모리 제한은 별도 기능이다. 이 변경만으로 서비스의 60초 상한을 보장하지 않는다.
