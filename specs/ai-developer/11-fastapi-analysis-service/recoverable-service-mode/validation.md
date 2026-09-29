# 검증 기록

## 구현 상태

- 기본값 `AGENTFIT_ANALYSIS_MODE=default`에서는 기존 SolarAnalyzer와 3키 Worker 요청을 유지한다.
- `AGENTFIT_ANALYSIS_MODE=recoverable-solar`일 때만 Worker에 모드를 전달하고 RecoverableSolarAnalyzer를 실행한다.
- 자식 결과의 `failed` 및 `needs_confirmation`은 복구 모드에서만 허용하며 정확한 키 집합, 형식, 안전 오류 코드를 확인한다. HTTP 경계가 Profile·질문을 다시 검증한다.

## 검증

- Worker 선택·미지원 모드 거절, 기본 프로세스의 초안 거절, 복구 초안 전달, HTTP 환경 설정 경로를 단위 테스트로 확인했다.
- 실제 로컬 HTTP → 자식 프로세스 → Worker → HTTP 경계를 가짜 분석기로 실행했다. `needs_confirmation`과 제안 값 확인 질문을 관측했고 외부 Provider를 호출하지 않았다.
- 전체 AI 서비스 단위 테스트 538건과 `git diff --check` 통과.

## 남은 조건

- 이 모드는 명시적 로컬 실험용이다. Spring의 사용자 확인·저장 금지 계약 및 UI가 준비되기 전 운영 활성화는 금지한다.
- 수정 후 Solar 실제 20건 평가는 합성 원문의 Upstage API 전송 승인을 기다리며 미실행이다. 의미 근거와 제안 값의 독립 채점도 필요하다.
