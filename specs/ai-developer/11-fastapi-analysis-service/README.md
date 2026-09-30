# FastAPI 내부 분석 서비스

Spring Boot → FastAPI 경계의 AI 측 구현 제안이다. 팀 간 DTO 합의 전까지 공개 API로 취급하지 않는다.

## 로컬 실행

`ai_service/`에서 의존성을 설치한다.

```powershell
python -m pip install -r requirements.txt
```

실행 프로세스의 환경 변수에 `AGENTFIT_INTERNAL_TOKEN`과 `UPSTAGE_API_KEY`를 설정한 뒤 시작한다. `.env` 파일은 자동 로드하지 않는다.

```powershell
python -m uvicorn agentfit_ai.http_service:app --host 127.0.0.1 --port 8000
```

`GET /healthz`는 프로세스 생존 여부만 반환한다. `POST /internal/v1/analyze`는 [명세](spec.md)의 Bearer 인증·문서 헤더와 원문 body를 사용한다. 응답의 `complete`는 Profile 초안 후보이며 저장 완료를 뜻하지 않는다. 본문·LLM 원본 응답은 서비스가 저장하지 않는다.

기본 경로는 SolarAnalyzer를 사용한다. `recoverable-solar` 모드는 confirmation-v1, `integrated-candidates` 모드는 [confirmation-v2 통합 후보 분석](integrated-confirmation-service/spec.md)을 선택한다. v2는 LangExtract1.7.0과 Solar/NVIDIA 키가 필요하고, 근거 있는 non-null 불확실 제안도 보존한다. 실제 운영 적용은 품질 검증과 Spring 계약 확인 후 결정한다.

동시 분석 수와 업로드 기한은 [수용 제한 명세](../12-analysis-admission-control/spec.md)를 따른다.

기본 Solar 분석은 [요청 수명주기 명세](../13-analysis-request-lifecycle/spec.md)에 따라 요청별 프로세스로 실행된다. 전체 기한의 기본값은 60초이며 `AGENTFIT_REQUEST_TIMEOUT_SECONDS`로 1~120초를 설정할 수 있다.

통합 모드는 같은 요청별 프로세스 안에서 두 Provider를 직접 호출한다. 전체 기한은 기본1800초·1~3600초이며, 정확한 `X-AgentFit-Analysis-Contract: confirmation-v2` 헤더가 필요하다. 상세 설치·응답·오류는 [루트 실행 안내](../../../README.md#통합-확인형-서비스--선택형-로컬-실행)를 참고한다.

## 검증

`requirements-dev.txt`를 설치한 환경에서 `python -m unittest discover -s tests -q`를 실행한다. 실제 Provider 호출과 Spring 저장 검증은 이 HTTP 경계 테스트에 포함되지 않는다.
