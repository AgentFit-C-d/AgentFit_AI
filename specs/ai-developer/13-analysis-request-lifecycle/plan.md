# 구현 계획

1. Worker 입출력 계약을 `analysis_worker.py`와 `analysis_process.py`로 나눈다. 전자는 Solar 실행과 안전한 직렬화, 후자는 ASGI 부모에서 단일 프로세스의 생성·기한·취소·출력 크기·회수를 담당한다.
2. `solar.py`에 Worker 내부 전용 인라인 Provider 전송을 추가한다. 기존 `provider_worker._fetch`의 요청·응답 검증을 재사용해 오류 코드 매핑을 맞춘다. 기본 `post_solar`는 변경하지 않는다.
3. `http_service.py`는 기본 분석기일 때만 프로세스 러너를 호출한다. 업로드 시작 시 전체 deadline을 정하고 업로드·추출·분석에 남은 시간을 전달한다. 문서 본문 수신 후에는 ASGI disconnect를 관측해 실행 중인 Worker를 종료한다. 주입 분석기는 기존 테스트 계약을 유지한다.
4. 각각의 동작을 실패 테스트부터 추가한다. 프로세스 경계 테스트는 실제 느린 Worker와 로컬 소켓을 사용해 종료 여부를 확인하고, 세부 오류는 작은 단위 테스트로 보강한다.
5. 관련 테스트, 전체 AI 테스트, 로컬 Uvicorn smoke를 실행하고 결과를 `validation.md`에 기록한다. 독립 리뷰 후 `feature/analysis-request-lifecycle`에 커밋·push한다.

## 파일 책임

- `ai_service/agentfit_ai/analysis_worker.py`: 입력 계약 검증, 기본 Solar 분석, 제한된 안전 출력.
- `ai_service/agentfit_ai/analysis_process.py`: 요청별 단일 자식 프로세스의 생성·통신·종료·회수.
- `ai_service/agentfit_ai/solar.py`: Worker 내부 인라인 HTTP 전송 어댑터.
- `ai_service/agentfit_ai/http_service.py`: 전체 기한과 연결 종료를 ASGI 요청에 연결.
- `ai_service/tests/test_analysis_process.py`, `ai_service/tests/test_http_service.py`: 프로세스/HTTP 회귀.

## 구현 순서의 검증 기준

각 단계에서 먼저 실패를 재현하고 필요한 코드만 추가한다. 프로세스가 끝나지 않는 실패 테스트에는 별도 외부 테스트 기한을 두어 전체 테스트가 멈추지 않게 한다. 키와 원문은 테스트용 문자열만 사용한다.
