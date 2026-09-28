# 문서 입력 검증·추출 명세

## 목적과 범위

AI 분석기가 받기 전에 PDF·Markdown·직접 텍스트를 하나의 검증된 Unicode 문자열로 만든다. 이 모듈은 FastAPI 내부에서 호출할 순수 입력 경계이며 Spring 인증·저장·공개 HTTP 형식을 정하지 않는다. PDF·Markdown·직접 텍스트의 길이와 추출 상태를 실제 바이트·문자 기준으로 판정한다.

## 결정과 근거

- Python 3.12와 `pypdf==6.19.0`을 사용한다. PDF 처리는 15초 기한의 자식 프로세스에서 실행해 시간 초과 시 프로세스를 종료한다. 동일 프로세스 추출은 무한 대기 시 서비스 기한을 지킬 수 없어 채택하지 않는다.
- PDF 원본은 표준 입력으로 Worker에 전달하고 추출 문자열은 JSON으로 받는다. 원문·추출문을 파일·DB·일반 로그에 쓰지 않는다. Worker에는 API 키를 포함한 부모 환경을 전달하지 않는다.
- PDF 이미지는 OCR하지 않는다. `pypdf`의 텍스트 추출은 이미지와 의미 구조를 보장하지 않으므로 PDF의 의미 정확도는 별도 평가한다. 자식 프로세스는 시간 격리이며 메모리 제한 보장이 아니다.

## 입력과 반환

- `extract_document(kind, content)`에서 `kind`는 `PDF`, `MARKDOWN`, `TEXT` 중 하나다. PDF·Markdown은 `bytes`, 직접 텍스트는 `str`을 받는다. 타입 불일치와 다른 종류는 안전한 오류 코드로 거부한다.
- PDF·Markdown 파일 원본은 각각 10,485,760 bytes 이하이고 포함 경계는 허용한다. 직접 텍스트는 100,000 Unicode code points 이하이며, UTF-8 인코딩 가능한 문자열이어야 한다. Markdown은 UTF-8 strict decode로 처리하고 파일 bytes의 선두 UTF-8 BOM만 제거한다.
- 결과에는 파일 원본 bytes와 별도 인용문 없이 `kind`, `text`, `byte_size`, `character_count`, `page_count`, `page_spans`를 제공한다. `text`는 분석 호출 동안에만 보유하는 추출 원문이다. 텍스트·Markdown의 `page_count`는 `None`, `page_spans`는 빈 배열이다. PDF의 각 페이지 근거는 `{"page": 1, "start": 0, "end": 10}` 형태의 1부터 시작하는 페이지 번호와 결합 텍스트의 0부터 시작하는 `start`·끝 제외 `end` 범위다. 페이지는 `\n` 한 글자로 연결하며 이 구분자도 전체 문자 수에 포함한다.
- 분석할 수 있는 글자가 없는 공백 입력과 공백만 추출된 PDF는 거부한다. 반환 텍스트는 공백을 자동 trim하거나 정규화하지 않는다.

## PDF 판단

- `%PDF-` 시그니처를 확인하고 100쪽 초과·암호 잠금·손상·전체 빈 텍스트를 구분한다. 100쪽은 허용한다. 텍스트가 있는 페이지와 없는 페이지가 섞이거나 한 페이지라도 공백만 추출되면 부분 추출로 거부한다. 자동 절단하지 않는다.
- 페이지 순서대로 텍스트를 추출하고 결합 결과가 100,000 code points를 넘는 즉시 거부한다. `pypdf`가 예외를 내거나 Worker가 비정상 종료하면 원문 없는 안전 코드만 반환한다.
- Worker는 15초 안에 끝나야 한다. 시간 초과 시 종료·회수한 뒤 `PDF_TIMEOUT`을 반환한다. 자식 프로세스 출력은 최대 결과 크기에 해당하는 내부 계약으로 검증한다.

## 오류 계약

`DocumentExtractionError.code`는 `INVALID_DOCUMENT_KIND`, `INVALID_DOCUMENT_CONTENT`, `DOCUMENT_TOO_LARGE`, `DOCUMENT_TEXT_TOO_LONG`, `DOCUMENT_INVALID_UTF8`, `DOCUMENT_EMPTY`, `PDF_INVALID`, `PDF_LOCKED`, `PDF_TOO_MANY_PAGES`, `PDF_PARTIAL_TEXT`, `PDF_TIMEOUT`, `PDF_WORKER_FAILED` 중 하나다. 예외 메시지·로그·반환 메타데이터에 원문·추출문·키를 넣지 않는다. Spring 공개 코드 매핑은 후속 내부 HTTP 계약에서 정한다.

## 검증과 남은 경계

- 실제 합성 PDF로 정상·암호·빈 페이지·혼합 페이지·101쪽·손상·시간 초과를 검증한다. Markdown invalid UTF-8, 모든 입력의 포함/초과 문자 경계, 원문·키 비노출을 검사한다.
- 이 기능만으로 AD006 전체가 끝나지 않는다. FastAPI 요청 취소·body 스트리밍 제한과 60초 전체 기한, OS 수준 Worker 메모리 격리, Spring 연동은 후속 계약·서비스 기능에서 구현·검증한다.
