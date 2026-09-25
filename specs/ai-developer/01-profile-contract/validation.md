# AI Profile 후보 검증 결과

**2026-09-25 로컬 실행**

- SDD: [Spec](spec.md) → [Plan](plan.md) → [Tasks](tasks.md) 작성 후 구현했다. 구현 전 첫 테스트 실행은 `ModuleNotFoundError: agentfit_ai`로 실패해 미구현 상태를 확인했다.
- 실행 환경: 번들 Python 3.12.14, 추가 패키지 설치 없음.
- 명령: `python -m unittest discover -s tests -v` (`ai_service/`에서 실행).
- 결과: 10개 테스트 통과. 합성 사례 3건, 필드 누락·타입·공백/길이·배열 길이, `null`/`[]`, 근거 누락·불일치·범위, Unicode code-point 위치, 안전 오류를 확인했다.
- 한계값 테스트를 추가한 첫 실행은 테스트 도우미가 정답 객체를 공유·변경해 실패했다. 도우미가 정답을 복사하도록 수정한 뒤 10개 테스트를 다시 실행해 통과했다. 200 code points·배열 30개 허용과 초과 거부를 확인했다.

## 검증하지 않은 범위

- 근거 문구가 의미상 현재 프로젝트의 확정 사실인지 판단하지 않는다. 후보/부정/다른 대상·상충 사례의 정답 평가는 별도 의미 검증 단계가 필요하다. `[]`의 명시적 없음도 현재 모듈은 근거 위치의 존재만 확인한다.
- FastAPI HTTP, Solar 응답 변환, PDF 추출, Spring Boot 최종 검증·PostgreSQL 저장, 오류 진단 7일 보관과 공개 UI는 연결하지 않았다.
- 기존 Solar smoke test 1건은 별도 [Provider 평가 기록](../provider-evaluation.md)에 있고 이 모듈의 통합 테스트가 아니다.
