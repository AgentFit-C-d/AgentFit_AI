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

기본 경로는 SolarAnalyzer를 사용한다. 확인 질문(`needs_confirmation`) 결과는 내부 계약에 대비한 응답 검증만 구현했으며, 실제 선택형 분석기의 운영 적용은 품질 검증 후 결정한다.

## 검증

`requirements-dev.txt`를 설치한 환경에서 `python -m unittest discover -s tests -q`를 실행한다. 실제 Provider 호출과 Spring 저장 검증은 이 HTTP 경계 테스트에 포함되지 않는다.
