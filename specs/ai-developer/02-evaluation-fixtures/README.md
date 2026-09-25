# 평가 사례와 사전 정답

- 합성 FACT 최소 9개, SEM 최소 12개, NORMAL 최소 30개와 ERROR 사례를 설계한다.
- AI 출력 확인 전에 정답·입력 분포·필수 사실·집계 기준을 고정한다.
- 연결 작업: T016. 구현 fixture는 승인된 작업에 따라 `tests/fixtures/`에 둔다.

## 시작 사례

[starter-cases.json](starter-cases.json)에 합성 직접 텍스트 3건과 **모델 호출 전에 고정한 정답**을 넣었다. `expected`는 Profile의 10개 값을 모두 포함한다. `null`은 문서에서 확정할 수 없는 값이고, 배열은 문서에서 확정된 항목만 담는다.

`evidenceQuotes`는 테스트 준비용 원문 조각이다. 실제 FastAPI 결과에는 인용문 대신 해당 조각이 위치한 문서의 code-point `start/end`를 반환하고 원문과 대조해야 한다. 후보·과거 시스템 정보처럼 문서에 단어가 있어도 현재 프로젝트의 확정값이 아니면 `null`로 남긴다.

이 3건은 작업 시작 예시이며 FACT 9개·SEM 12개·NORMAL 30개 목표를 채운 것이 아니다. PDF·Markdown과 오류 사례를 추가할 때도 입력과 기대값을 먼저 작성한 뒤 모델을 실행한다. 기존 T016은 단일 Next.js 서버 기준이므로 새 [AD003](../tasks.md)으로 재배정했다.
