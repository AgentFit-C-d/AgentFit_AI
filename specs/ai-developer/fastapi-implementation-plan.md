# AI Developer FastAPI 구현 계획

**상태:** 확정된 서비스 분리를 반영한 AI 파트 계획. 내부 HTTP schema·인증·timeout 등은 Full Stack A와 공동 계약 전까지 초안이다. 애플리케이션 코드와 서버 실행 결과는 아직 없다.

## 목표와 경계

Next.js → Spring Boot → FastAPI 흐름에서 FastAPI는 단일 문서의 텍스트 추출, Provider 분석, 구조·근거·의미 검증을 수행한다. 출력은 검증된 Profile 초안 후보 또는 안전한 실패다. Spring Boot가 인증·프로젝트 소유권·최종 검증·PostgreSQL 저장·공개 성공 상태를 맡는다. FastAPI에 DB 연결을 두지 않는다.

## 작업 순서

1. Full Stack A와 내부 요청/응답, 서비스 인증, 입력 상한, 오류 코드, timeout·취소·재시도, 진단 응답 전달·삭제 책임을 합의한다. 공개 API가 저장 성공을 확인한 뒤에만 성공을 반환하도록 상태 전이를 고정한다.
2. 사전 정답이 있는 합성 PDF·Markdown·텍스트 사례를 고정한다. FACT 9개, 의미 반례 12개, 정상 30개와 오류 사례를 구분한다.
3. FastAPI의 입력 제한·PDF 추출·부분 추출 판단·취소/timeout 정리를 구현한다. 원문은 처리 종료 후 별도 보관하지 않는다.
4. Provider 추상화와 Solar Pro 4 첫 평가를 진행한다. 평가 결과로 분석 모델을 결정한 뒤 구조화 출력·거절·불완전 응답을 처리한다.
5. 값·출처·근거 위치·미정 일관성 및 부정/후보/미래/다른 대상/상충 문맥 검증을 구현한다. 실패는 안전한 코드로 반환한다.
6. 실패 건에서 수신한 LLM 원본 응답만 별도 진단 경로로 Spring Boot에 전달한다. 정상 응답은 보관하지 않는다. 7일 만료·프로젝트 삭제는 Spring Boot와 통합 검증한다.
7. 단위·계약·통합 검증 후 실제 Provider·Spring 저장·Frontend 표시가 연결된 전체 평가를 수행한다. Mock, 실제 API, 실제 DB·화면 결과를 분리 기록한다.

## 완료 판단

- 내부 계약의 요청/응답·오류·보관 조건을 Full Stack A와 같은 테스트 사례로 검증한다.
- 입력 한계(10 MiB PDF, 100쪽, 100,000 code points), 구조·근거·의미 검증, 안전한 오류 및 Secret/지시 주입 방어를 확인한다.
- 실제 연결에서 사전 정답 정확도, 첫 요청 저장·표시 성공률, 사용자 관측 60초 결과/실패 안내를 기존 [Spec](../001-project-document-analysis/spec.md)의 기준으로 판정한다.
- FastAPI 성공만으로 DB 저장·사용자 표시 성공을 선언하지 않는다. 운영 배포·외부 Provider·실제 사용자 검증이 없으면 미완료로 남긴다.

세부 작업은 [AI Developer Tasks](tasks.md), 서비스 경계는 [계약 초안](fastapi-service-contract.md)을 따른다.
