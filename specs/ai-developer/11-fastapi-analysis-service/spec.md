# FastAPI 내부 분석 서비스 명세

상태: AI 팀 구현 제안. Spring Boot와 HTTP DTO·인증·기한은 합의 전이며 공개 API가 아니다.

## 목적

Spring Boot가 전달한 한 문서를 추출·분석해 검증된 Profile 초안 후보 또는 안전한 실패 코드를 반환한다. FastAPI는 사용자 인증, 소유권 판단, PostgreSQL 저장, 저장 완료 응답을 수행하지 않는다.

## 내부 HTTP 계약 제안

- `POST /internal/v1/analyze`의 body는 PDF·Markdown·직접 텍스트 원문 bytes다. `X-Document-Kind`는 `PDF|MARKDOWN|TEXT`, `X-Document-Id`는 영문/숫자/`_`/`-` 1~128자, `X-Request-Id`도 같은 형식이다.
- `Content-Type`은 각각 `application/pdf`, `text/markdown; charset=utf-8`, `text/plain; charset=utf-8`이다. 텍스트의 UTF-8 BOM은 허용한다. 압축된 요청 body는 허용하지 않는다.
- `Authorization: Bearer <AGENTFIT_INTERNAL_TOKEN>`을 추출·분석 전에 검사한다. 토큰 설정이 없으면 서비스는 분석 요청을 받지 않는다.
- 실제 스트림으로 읽은 body가 10 MiB를 초과하면 413으로 거절한다. `Content-Length`는 빠른 거절에만 사용한다. 문서 추출의 100,000 code point·PDF 100쪽 제한을 재사용한다.
- 정상 응답은 `requestId`, `outcome=complete|needs_confirmation|failed`와 해당 분석 결과를 담는다. complete도 저장되지 않은 초안 후보이며 Spring이 재검증·저장한 후 공개 성공을 결정한다.
- 현재 기본 분석기는 SolarAnalyzer이므로 `complete` 또는 `failed`만 생성한다. `needs_confirmation`은 검증된 선택형 분석기를 연결할 때 사용할 내부 응답 계약이며 현재 기본 경로에서 생성된다고 주장하지 않는다.
- 거부·오류 응답에는 문서 원문, API 키, LLM 원본 응답, Python 예외 문자열을 담지 않는다. 예상하지 못한 예외는 `INTERNAL_ERROR`로 처리한다.
- `GET /healthz`는 프로세스 응답만 확인한다. Provider·Spring·DB의 준비 완료를 의미하지 않는다.

## 수용 기준

1. 인증 실패와 과대 body는 분석기를 호출하지 않는다.
2. 세 문서 유형이 기존 추출기를 통과하고 분석기에 동일한 `documentId`와 추출 텍스트를 전달한다.
3. 결과와 오류가 명시적 상태로 매핑되고, 원문·키·LLM 응답은 오류에 노출되지 않는다.
4. 서비스 프로세스를 로컬에서 실행하고 실제 HTTP 요청을 검증한다.

## 남은 연동·품질 게이트

- Spring Boot 팀과 DTO·토큰 전달·timeout·취소·재시도·저장 검증을 합의한다.
- 실패 LLM 원본 응답의 Spring 전송·7일 삭제 방식은 별도 합의와 구현이 필요하다.
- PDF worker의 OS 메모리 제한과 독립 문서의 정확도·오확정 0·60초 목표는 별도 검증 과제다.
