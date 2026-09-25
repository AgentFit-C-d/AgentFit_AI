# AI Developer — FastAPI 서비스 경계·계약 초안

**상태:** 2026-09-25 팀 검토 초안. 사용자 확인에 따라 Spring Boot와 FastAPI 분리는 확정이다. 이 저장소의 `Docs/`에서 스크린샷이 언급한 2026-09-23 아키텍처·모듈 원문은 아직 찾지 못했다. 아래 DTO·운영 세부사항은 합의 전 제안이며 공개 API가 아니다.

## 확정된 책임 경계

| 구성 요소 | 책임 |
| --- | --- |
| Next.js | 문서 입력, 분석·저장 상태와 검토 화면 |
| Spring Boot | 인증·프로젝트 소유권·비즈니스 규칙, 분석 요청 조율, 최종 검증, PostgreSQL 저장, 공개 API 응답 |
| FastAPI | 문서 텍스트 추출, AI Provider 호출, 구조·근거·의미 검증, 검증된 Profile **초안 후보** 또는 안전한 오류 반환 |

통신 순서는 Next.js → Spring Boot → FastAPI다. FastAPI는 PostgreSQL에 직접 접근하거나 저장 성공을 선언하지 않는다. Spring Boot의 저장 결과를 확인한 뒤에만 공개 API가 저장된 초안을 반환한다. AI 오류 또는 DB 저장 오류는 기존 확인 Profile을 바꾸지 않는다.

## Spring Boot → FastAPI 요청 제안

- 한 번의 요청에는 PDF·Markdown·직접 텍스트 중 하나만 전달한다. 원문의 크기·페이지·문자 수 제한은 기존 [Feature Spec](../001-project-document-analysis/spec.md)을 유지한다.
- Spring Boot가 사용자 인증·프로젝트 소유권·공개 요청 제한을 수행한다. FastAPI도 서비스 간 요청의 인증과 입력 제한을 검사한다. 사용자 OAuth 토큰과 DB 자격 증명은 전달하지 않는다.
- 요청 식별자, 입력 유형, 문서 식별자, 원문 bytes 또는 텍스트, 전체 기한·취소 신호를 전달할 방식은 합의해야 한다. 원문을 영구 큐·DB에 넣지 않는다.
- 내부 인증 방식, 재시도·멱등성, 전송 형식, 최대 body 크기와 timeout은 두 서비스의 계약 및 운영 환경을 확인한 뒤 확정한다.

## FastAPI → Spring Boot 결과 제안

- 정상 응답은 [공통 Profile](../001-project-document-analysis/data-model.md)의 10개 값과 필드별 출처·근거 위치를 포함한 **검증된 초안 후보**다. `null`은 미정, 빈 배열은 명시적으로 없음이다.
- 근거는 원문과 대조한 문서 ID·PDF 페이지 또는 전체 추출 텍스트의 code-point `start/end` 위치로 제한한다. `unknownFields`는 저장 계층에서 다시 계산한다.
- FastAPI는 입력 거부, 추출 실패, Provider 거절·장애·시간 초과, 구조 오류, 근거/의미 검증 실패를 원문·Secret이 없는 코드로 구분한다. 내부 코드와 Spring Boot의 공개 HTTP/code 매핑은 함께 확정한다.
- Spring Boot는 FastAPI 응답을 신뢰 경계 밖의 데이터로 다시 검증하고, 프로젝트·분석 generation·version을 확인한 뒤 짧은 트랜잭션으로 저장한다. 저장 실패 시 공개 응답은 성공이 아니다.
- **사용자 결정:** 분석 **실패 건**에서 LLM 원본 응답이 실제로 수신된 경우에만 오류 추적용으로 최대 **7일** 보관한다. Provider 호출 실패 등 응답이 없는 경우에는 빈 진단 기록을 만들지 않는다. 정상 분석의 원본 응답은 보관하지 않는다. 원본 응답에는 문서 내용이 포함될 수 있으므로 공개 응답·일반 오류·일반 로그·Audit·평가 파일에는 넣지 않는다. PostgreSQL 보관·만료 삭제는 Spring Boot가 담당하고 FastAPI는 DB에 접근하지 않는다. 내부 전송·접근 통제·암호화·삭제 방식은 계약 세부 설계에서 고정한다.

## 합의 후 고정할 항목

1. 아키텍처·AI 모듈 원문의 경로와 충돌하는 문구.
2. 내부 엔드포인트·요청/응답 schema·오류 코드·서비스 인증·timeout·취소·재시도·멱등성.
3. 실패 건의 원본 응답을 Spring Boot에 전달하는 조건, 7일 만료 삭제·접근·암호화 방식과 로그·추적·임시 파일의 잔존 범위.
4. Spring Boot의 최종 검증 항목, 저장과 공개 응답의 순서, 실패 시 상태 전이.
5. Solar Pro 4 평가 결과와 최종 Provider 선택. Solar Pro 4는 현재 첫 평가 후보다.

이 항목을 결정한 뒤 [기존 Plan](../001-project-document-analysis/plan.md), [Tasks](../001-project-document-analysis/tasks.md), [공개 API](../../Docs/api/01-project-analysis.md), OpenAPI, AI Developer의 기능별 README를 같은 계약으로 갱신한다.
