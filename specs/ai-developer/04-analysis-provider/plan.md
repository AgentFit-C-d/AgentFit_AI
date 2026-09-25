# Solar Profile 분석 계획

## 기술과 파일

Python 3.12 표준 라이브러리만 사용한다. 기존 Profile 검증기와 같은 패키지에 추가하며 HTTP 전송 함수를 주입해 네트워크 없는 테스트를 만든다.

- ai_service/agentfit_ai/solar.py: Prompt·strict JSON Schema·HTTP·오류 변환·근거 위치 연결
- ai_service/agentfit_ai/evaluate.py: 합성 사례 전용 실제 호출 실행기
- ai_service/tests/test_solar.py: 계약 및 실패 테스트
- ai_service/tests/fixtures/solar-cases.json: 사전 정답 6건

## 외부 계약과 설계 선택

[공식 Chat API](https://console.upstage.ai/api/chat)를 2026-09-25 확인했다.
고정 주소 https://api.upstage.ai/v1/chat/completions, model solar-pro4, strict json_schema, stream=false, max_tokens=4096을 사용한다. 최종 profile-v2는 reasoning_effort=medium, temperature=0을 명시한다. 초기 none 설정의 실패도 평가 기록에 보존한다.
API 키는 Authorization에만 넣는다. 도구 호출을 제공하지 않고 문서 지시는 데이터로 취급한다.
원문은 user 메시지에만, 추출 규칙은 system 메시지에 둔다.
Provider 인용을 모델 생성 offset으로 신뢰하지 않고 Python 문자열 위치로 계산한다. 같은 인용이 반복되면 더 긴 고유 근거가 필요하므로 실패시킨다.

기본 HTTP timeout은 40초이며 자동 재시도와 redirect를 하지 않는다. 응답은 1MiB로 제한한다.
표준 라이브러리 socket timeout은 전체 사용자 관측 60초 SLA 보장이 아니다. 강제 전체 deadline·취소 전파는 FastAPI 통합에서 다룬다.
실패 원본 응답을 파일이나 일반 로그에 쓰지 않는다. 팀이 확정한 실패 응답 7일 보관은 Spring Boot 진단 경로가 준비되면 별도 계약으로 연결한다.

## 검증 및 Constitution 점검

III: strict schema와 독립 검증기, 미정 유지. V: 현재 키·명확한 Secret 차단과 안전한 오류.
VIII: 텍스트 분석 경로만 추가. IX: 사전 정답과 실제/Mock 분리.
문자열 검사만으로 의미의 참/거짓을 증명하지 않는다. 의미 지시는 Prompt와 사전 정답 평가로 확인하고 한계를 결과에 기록한다.
전체 Profile 후보의 구조·근거를 확인한 결과만 반환하며 저장은 하지 않는다.

## 실행

ai_service에서 python -m unittest discover -s tests -v
실제 합성 평가: python -m agentfit_ai.evaluate --live
키는 UPSTAGE_API_KEY 환경변수 또는 저장소 루트 .env에서 읽으며 화면/파일에 출력하지 않는다.

## 최신 구현
위 v2 설정은 최초 기능 기록이다. 안정화 후 profile-v4, reasoning_effort=none, 필드별 null/known 응답을 사용한다. stability/plan.md 및 stability/validation.md 참조.
