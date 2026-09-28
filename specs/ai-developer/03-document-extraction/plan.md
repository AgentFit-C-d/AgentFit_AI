# Document Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDF·Markdown·직접 텍스트를 한도·추출 상태를 검증한 문자열로 변환한다.

**Architecture:** 파일 입력 검증과 결과 DTO는 `document_extraction.py`에 둔다. PDF 파서는 `pdf_worker.py`의 별도 Python 프로세스에서 실행하며 표준 입출력의 제한된 JSON 계약으로 통신한다. 추출 결과만 분석기로 전달하고 저장은 하지 않는다.

**Tech Stack:** Python 3.12, unittest, pypdf 6.19.0, 표준 라이브러리 subprocess.

**Spec:** `specs/ai-developer/03-document-extraction/spec.md`

## Global Constraints

- 파일 최대 10,485,760 bytes, PDF 최대 100쪽, 추출·직접 텍스트 최대 100,000 code points. 포함 경계 허용, 자동 절단 금지.
- PDF Worker 15초 제한. 원문·추출문·Credential의 디스크·일반 로그 기록 금지.
- 현재 FastAPI·Spring 서비스 계약은 바꾸지 않는다. 이 기능의 반환은 분석 초안 저장 성공을 뜻하지 않는다.

## Review Focus

- `TEXT`의 한글·이모지 길이: code point 기준으로 계산하고 UTF-8 바이트 수와 혼동하지 않는 테스트.
- PDF 페이지 경계: 페이지 구분 `\n` 때문에 100,000자를 넘으면 오류를 내는 테스트.
- 정상 페이지 뒤 빈 페이지: 앞쪽 부분 결과를 반환하지 않는 테스트.
- PDF Worker 중단: 제한 시간을 넘으면 자식을 종료하고 원문 없는 코드만 반환하는 테스트.
- 암호 PDF·깨진 UTF-8·손상 PDF: 각각 구분되는 안전 코드와 원문 비노출 테스트.

---

### Task 1: 텍스트와 Markdown 입력 경계

**Files:** Create `ai_service/agentfit_ai/document_extraction.py`; create `ai_service/tests/test_document_extraction.py`; create `ai_service/requirements.txt`.

**Interfaces:** `extract_document(kind: str, content: bytes | str) -> ExtractedDocument`; `DocumentExtractionError.code`; `ExtractedDocument(kind, text, byte_size, character_count, page_count, page_spans)`.

- [x] 테스트 작성: 종류·타입·빈 내용·UTF-8 오류·10 MiB 파일 경계·100,000 code point 경계와 원문 비노출.
- [x] 테스트가 기능 부재로 실패하는지 실행해 확인.
- [x] TEXT/MARKDOWN 검증·결과 반환과 `pypdf==6.19.0` 의존성을 구현.
- [x] 대상 테스트 통과를 확인.

### Task 2: PDF Worker와 안전한 오류

**Files:** Create `ai_service/agentfit_ai/pdf_worker.py`; modify `ai_service/agentfit_ai/document_extraction.py`; modify `ai_service/tests/test_document_extraction.py`.

**Interfaces:** Parent calls `python -m agentfit_ai.pdf_worker` with PDF bytes on stdin; Worker writes one JSON response with `text`, `page_spans`, `page_count` or `error` to stdout. `extract_document` validates the response.

- [x] 실제 합성 PDF 테스트 작성: 텍스트 1·2쪽, 잠금, 손상, 빈/혼합 페이지, 101쪽, 출력 상한, Worker 시간 초과.
- [x] 대상 테스트가 PDF 미지원으로 실패하는지 확인.
- [x] Worker에서 시그니처·잠금·쪽수·페이지 텍스트·전체 길이를 검사. 부모에서 15초 timeout과 종료 코드·JSON 구조를 검사.
- [x] 대상 테스트와 전체 단위 테스트 통과를 확인.

### Task 3: 통합 기록과 검증

**Files:** Modify `specs/ai-developer/03-document-extraction/README.md`; create `specs/ai-developer/03-document-extraction/validation.md`.

- [x] `python -m unittest discover -s tests`와 `git diff --check`를 실행.
- [x] PDF Worker가 원문·Credential을 출력·파일로 남기지 않는 테스트/검사를 수행하고 결과와 한계를 기록.
- [x] 명세·코드·검증 문서만 `feature/document-extraction`에 커밋·push. 기존 미추적 상태 파일은 제외.
