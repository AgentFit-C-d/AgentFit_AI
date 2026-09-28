# 검증 기록

- 로컬 느린 응답 서버에서 `timeout=0.35`의 기존 구현은 약 1.56초 동안 전체 응답을 받아 테스트가 실패했다. 수정 후 같은 테스트는 `PROVIDER_TIMEOUT`으로 끝났다.
- 독립 리뷰가 첫 소켓 수정의 느린 헤더·조기 EOF와 두 번째 비동기 수정의 DNS executor 대기·압축 디코딩 위험을 지적했다. 느린 헤더(0.25초 제한인데 기존 1.04초), Content-Length 조기 EOF, gzip 응답을 실제 로컬 서버의 실패 테스트로 확인하고 프로세스 경계로 바꿨다.
- 정상 짧은 HTTP 응답은 bytes를 그대로 반환했다.
- HTTP status·network 오류·1 MiB 초과 응답, 정상·잘린 chunked 응답 테스트를 유지했다. Provider HTTP 경계 10건 통과.
- 전체 AI 테스트 479건 통과. 기존 평가 CLI의 예상된 `--live required` 출력은 있었고 종료 코드는 0이었다.
- 합성 문서 1건을 실제 Solar API로 호출해 Profile 분석 완료를 확인했다(3회 호출, 로컬 실행 약 24.5초). 실제 문서 품질을 검증한 결과는 아니다.
- 독립 재검토에서 추가 Critical/Important 결함을 찾지 못했다. 리뷰어는 테스트를 직접 재실행하지 않았다.

## 범위 제한

부모가 Provider 호출 자식 프로세스에 기한을 걸어 DNS·TLS·헤더·본문의 지연을 중단한다. OS의 프로세스 생성 단계는 Python `subprocess.run(timeout)`에 포함되지 않으므로 엄밀한 전체 wall-clock 상한은 아니다. 호출마다 Python 프로세스를 새로 띄우는 지연 비용도 있다. Spring 연결 종료 시 분석 전체 취소나 FastAPI 요청 집중 제어는 다루지 않는다.
