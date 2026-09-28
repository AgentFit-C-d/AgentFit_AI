# 계획

1. 느린 chunk 응답을 보내는 로컬 HTTP 서버를 테스트에 만들고 기존 `post_solar`가 기한을 넘기는 실패를 확인한다.
2. 첫 `urllib` socket 읽기 수정은 독립 리뷰에서 한 번의 헤더/chunk 파싱 내부로 deadline이 들어가지 못하고 조기 EOF 검출이 약해지는 결함이 확인됐다. 두 번째 HTTPX 비동기 수정도 DNS executor 종료 대기로 총 기한을 보장하지 못한다. 따라서 동기 `post_solar` 호출 형식은 유지하고, Provider HTTP 호출을 별도 프로세스에서 수행하며 부모가 `subprocess.run(timeout=...)`으로 전체 작업을 중단한다. 키와 요청은 stdin으로만 전하고, 자식 stdout은 성공 bytes 또는 안전 코드만 담는다.
3. EOF·정상 짧은 응답·응답 크기 초과·HTTP status·network 오류 회귀 테스트를 실제 로컬 서버로 통과시킨다. 자식 프로세스 환경에서 서비스 키를 제외한다.
4. 전체 AI 테스트와 실제 로컬 HTTP 검증, diff 점검, 독립 리뷰 후 브랜치를 push한다.
