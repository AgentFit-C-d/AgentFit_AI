# Document Input Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Direct implementation is already authorized. Steps use checkbox syntax.

**Goal:** PDF·Markdown의 분석→사용자 수정→mock 저장을 실제 파서·SDK·자식 프로세스로 검증한다.

**Architecture:** 기존 core_flow/provider/sample_pdf fixture를 재사용하고 core_flow_tests에 시험만 추가한다. 외부 모델 대신 loopback 응답을 사용한다.

**Tech Stack:** Python unittest, httpx, pypdf, FastAPI, LangExtract 1.7.0.

**Spec:** specs/ai-developer/document-input-runtime/spec.md

## Global Constraints

- 공개 API·기본 서비스·의존성·실제 평가 소스는 바꾸지 않는다.
- 추가 외부 모델 호출 0, 유료 사용 0, 자동 재시도 0, 배포 0.
- 로컬 HTTP: AI 30초/mock 45초/client 50초. 대상 검사 120초, 최종 네 suite 각각 180초, CI 관찰 10분.
- 실패로 제품 결함이 확인될 때에만 재현 테스트 후 최소 수정한다.
- 테스트 추가가 전부라면 기존 동작의 GREEN을 기록한다. 제품 결함의 RED를 만들어 냈다고 주장하지 않는다.

## Review Focus

1. BOM·이모지·CRLF 때문에 byte/문자 위치가 섞이는 경우: Markdown 실제 공개 흐름에서 고정 위치를 검사한다.
2. 여러 PDF 페이지 근거 위치: 두 페이지 실제 추출 후 고정 위치와 확인 저장 후 보존을 검사한다.
3. 파서 실패가 기존 데이터나 모델 호출에 영향을 주는 경우: 오류 종류별 이전 값 보존·호출 수·명시적 재입력을 검사한다.
4. 성공 입력과 실패 원문 저장: 전체 합성 원문/키 sentinel을 mock 상태·오류에서 검사한다. 운영 로그는 미검증으로 남긴다.
5. PDF 문서 메타데이터: 기존 null 계약을 실측값으로 오인하지 않도록 결과·인계 문서에 명시한다.

### Task 1: 문서 입력 통합 회귀 시험

**Files:**
- Create: ai_service/core_flow_tests/test_document_input_runtime.py
- Modify: Docs/api/core-analysis-mock-handoff.md
- Create: specs/ai-developer/document-input-runtime/validation.md

**Interfaces:**
- Consumes: core_flow(provider, analysis_mode='integrated-nvidia'), confirm(http, project_id, draft, **changes), Provider(), sample_pdf(pages: list[str]) -> bytes.
- Produces: unittest discovery로 실행되는 통합 테스트와 검증 기록. 제품 인터페이스 변경 없음.

- [ ] Step 1: `test_markdown_unicode_bom_crlf_survives_confirmation` 작성. 원문 `# 기획 😀\r\nTestApp\r\nReact\r\n기록 저장`에서 frontend 근거 [17,22), features [24,29), byteSize에는 BOM 포함, characterCount 29. DRAFT 자동 확정 금지, 수정 frontend USER/근거[], 유지 features DOCUMENT/근거 유지, 재조회·버전 충돌·삭제 확인.
- [ ] Step 2: `test_two_page_pdf_evidence_survives_confirmation` 작성. `TestApp`, `React Save records` 두 페이지에서 frontend [8,13), features [14,26), 모델 입력 전체 `TestApp\nReact Save records`; 문서 메타 null 표시, 저장 후 근거 보존 확인.
- [ ] Step 3: `test_invalid_documents_preserve_saved_profile_without_model_calls` 작성. UTF-8/빈 입력/문자 한도 및 PDF 손상/암호화/빈 페이지/부분 텍스트/페이지 한도 거절, 저장 상태·버전 보존, 원문 노출 금지, 유효 입력 명시적 재시도 성공.
- [ ] Step 4: 대상 실행: `python -m unittest discover -s core_flow_tests -p test_document_input_runtime.py -v` (공유 Python 실행 파일, 작업 디렉터리 ai_service).
  Expected: 세 시험 성공. 실패 시 원인을 조사하며 fixture 결함과 제품 결함을 구분한다.
- [ ] Step 5: 인계 문서에 합성 검증·실제 Spring 미검증·PDF metadata null을 기록하고 변경을 commit한다.
- [ ] Step 6: task-done에서 unit/runtime/contract/core 네 suite를 각각 한 번 실행하고 tail과 exit code를 확인한다.
  Expected: 각 suite exit 0. 플랫폼 skip과 경고는 기록한다.
- [ ] Step 7: 전체 브랜치를 한 번 독립 리뷰받고 중요한 지적만 RED→GREEN 수정한다. feature/document-input-runtime push 후 정확한 SHA의 CI 확인.
