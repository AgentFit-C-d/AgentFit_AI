# 문서 추출

- PDF·Markdown·직접 텍스트에서 분석 가능한 텍스트를 추출한다.
- 잠금·손상·빈 내용·부분 추출을 정상 분석과 구분하고 입력 한도를 검증한다.
- FastAPI가 추출 실행과 PDF 처리 종료를 책임지고, Spring Boot는 공개 입력·소유권 검사와 서비스 호출을 맡는다. 내부 전송·취소 계약은 [서비스 경계 초안](../fastapi-service-contract.md)에서 정한다.
- 기존 연결 작업 T017, T019–T020은 단일 Next.js 서버 계획의 항목이므로 재배정 전에는 구현 경로로 사용하지 않는다.

## 현재 구현

`ai_service/requirements.txt`의 `pypdf==6.19.0`을 설치한 뒤 `agentfit_ai.document_extraction.extract_document(kind, content)`를 호출한다. `TEXT`는 Python 문자열, `MARKDOWN`·`PDF`는 파일 bytes를 받는다. 반환값은 검증된 텍스트와 문자·바이트 수, PDF 페이지별 근거 위치다. 오류는 원문 없는 `DocumentExtractionError.code`로 구분한다.

PDF는 별도 프로세스에서 처리하며 15초를 넘기면 종료한다. 원문·추출문을 파일에 쓰지 않고 Worker 환경에 Provider 키를 전달하지 않는다. 이 모듈은 아직 FastAPI HTTP 엔드포인트에 연결되지 않았다. 서버 요청 취소와 body 스트리밍·OS 메모리 한계는 연동 작업에서 보완해야 한다.

[명세](spec.md) · [계획](plan.md) · [검증](validation.md)
