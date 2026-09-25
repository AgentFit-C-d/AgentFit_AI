# 검증 기록 — 2026-09-25

## 결과

- 구현 전 Solar 테스트는 모듈 부재(ModuleNotFoundError)로 실패했다.
- 최종 코드에서 `python -m unittest discover -s tests -v`: 23건 통과 (기존 Profile 10 + Solar 13).
- 실제 Solar 합성 평가: profile-v1 0/6, profile-v2 5/6. 각각 live-results-v1.json, live-results-v2.json에 최초 결과를 보존한다.
- v2 TEXT-SEM-002는 project_name 불일치다. 추가 진단 호출에서는 기대값과 일치했지만 최초 실패를 통과로 바꾸지 않았다. 원래 불일치 값은 로그하지 않아 정확한 오추출 형태는 미확인이다.
- v1 이후 진단 2회, v2 이후 진단 1회 포함 이 기능 개발에서 총 15회 호출했다. 검증 실패 응답의 사용량은 기록되지 않아 보고서 토큰 합계를 전체 청구량으로 해석하면 안 된다.
- 정답은 첫 호출 전에 고정했으며 튜닝 중 수정하지 않았다. 동일 사례를 튜닝에 사용했으므로 독립 검증 성적이 아니다.

## 원인과 변경

v1에서 미정 필드 근거 첨부, 언급 없는 배열을 [] 처리, 인용 불일치 및 이름/도메인 불일치가 발생했다.
v2는 한국어 규칙과 별도 형식 예시로 null/[] 및 인용 규칙을 명확히 하고 reasoning=medium, temperature=0으로 변경했다.
검증기 거부 조건은 완화하지 않았다. v2 6건 지연은 약 13.3~20.5초이며 작은 개발 표본이다.

## 명세·구현·작업 교차 점검

| 항목 | 구현과 근거 |
|---|---|
| SA01 | 입력 길이/ID/알려진 비밀 패턴을 호출 전 검사. Secret 탐지는 완전한 DLP가 아니다. |
| SA02 | 전체 10필드 strict schema와 추출 프롬프트. 의미 정확도는 5/6으로 미충족 사례가 남는다. |
| SA03 | 고유 인용만 code-point 위치로 변환. Unicode·없는/중복 근거 테스트. |
| SA04 | 기존 validate_profile 통과 후 초안만 반환. 원본 응답/인용 미반환. |
| SA05 | HTTP/timeout/refusal/truncation 고정 코드, 재시도/redirect 없음. 관련 테스트. |
| SA06 | 사전 정답 6건과 버전별 실측 보고서 보존. |
| SA07 | 저장 성공/의미 진실성을 보장하지 않는 초안 계약. |

이 점검은 현재 기능의 수동 SDD 교차 점검이며 전역 Spec Kit CLI 실행 기록이 아니다.

## 남은 작업과 적용 제한

- 프로젝트명 추출의 반복 안정성과 독립 FACT9/SEM12/NORMAL30 품질 평가가 필요하다. 운영 정확도 승인이나 Solar 최종 채택 완료가 아니다.
- 현재는 Python 텍스트 분석 모듈이다. PDF, FastAPI HTTP, Spring Boot 최종 검증·저장은 후속 기능이다.
- 실패 원본 응답 7일 보관은 Spring 진단 저장 계약과 함께 구현해야 한다. 현재 디스크/일반 로그에 원본 응답을 저장하지 않는다.
- 40초는 socket timeout이며 전체 처리 deadline/SLA가 아니다.
- feature/profile-validation에서 분기했으므로 해당 선행 변경에 의존한다. main 병합·배포는 수행하지 않았다.
