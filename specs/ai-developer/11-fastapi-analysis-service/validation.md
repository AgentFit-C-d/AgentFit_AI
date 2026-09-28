# 검증 기록

- TDD: 모듈 부재, 잘못된 Profile 노출, 임의 확인 질문 노출, 긴 Content-Length 예외, 중복 인증 헤더 허용, 필드 상태 모순, 정규화된 확인 사유 거절을 각각 실패 테스트로 확인한 뒤 수정했다.
- 로컬 TestClient: PDF·Markdown·TEXT 추출, 10 MiB 실제 body 제한, 인증·헤더·UTF-8 오류, Profile 재검증, 확인 질문 검증, 예상 밖 예외의 안전 응답을 검사했다.
- 전체 단위 테스트: 최종 리뷰 수정 후 `python -m unittest discover -s tests -q` 472건 통과. 기존 평가 CLI의 예상된 `--live required` 출력은 있었고 종료 코드는 0이다.
- 실제 루프백 HTTP: Uvicorn 서버에서 `/healthz`, 인증 거절, 문서 분석 응답을 검증했다. Provider 호출은 합성 분석기로 대체했다.
- `pip check`: 의존성 충돌 없음.
- 독립 검토: `ANALYSIS_UNRESOLVED` 사유가 정상 확인 결과임에도 502로 거절되던 결함을 회귀 테스트로 고쳤다.

## 남은 위험

- 기본 분석기의 40초 설정은 전체 HTTP 응답의 강제 중단이 아니다. 느린 스트림, Spring 연결 종료, 요청 폭주에서 작업이 계속될 수 있다. 총 기한·취소·동시성 제한을 별도 운영 안정화 기능으로 구현해야 한다.
- PDF worker는 15초 제한이 있으나 OS 메모리 제한이 없다.
- Spring 계약·저장 검증, 실패 원본 응답 전송/7일 삭제, 독립 문서 품질·오확정 0은 검증되지 않았다.
