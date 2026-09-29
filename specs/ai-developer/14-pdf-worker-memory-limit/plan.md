# 구현 계획

1. `worker_memory.py`에 `apply_pdf_memory_limit(limit_bytes=512*1024*1024)`를 만든다. Windows Job Object 구조체·API 호출을 한 모듈에 가두고 Linux `resource.setrlimit`와 지원 OS 실패 경로를 분리한다.
2. `pdf_worker.py`의 `pypdf` import를 제한 적용 뒤로 옮긴다. `main` 시작에서 제한 적용이 실패하면 stdin을 읽지 않고 안전 오류 JSON을 출력한다. `MemoryError`도 안전 Worker 오류로 매핑한다.
3. Windows 실제 자식 프로세스에서 Job 설정 조회와 초과 할당 실패를 검증한다. 기존 PDF 정상·오류 테스트와 FastAPI PDF 경계 테스트를 실행한다.
4. 전체 AI 테스트·의존성 점검·diff 점검을 수행한다. 독립 리뷰를 시도하고 결과를 기록한 뒤 `feature/pdf-worker-memory-limit`에 커밋·push한다.

## 수정 파일

- `ai_service/agentfit_ai/worker_memory.py`: 플랫폼별 Worker 메모리 격리.
- `ai_service/agentfit_ai/pdf_worker.py`: 파싱 전에 제한 적용 및 안전 오류.
- `ai_service/tests/test_worker_memory.py`: 실제 자식의 제한·실패 경로.
- `ai_service/tests/test_document_extraction.py`: 기존 추출 회귀 및 오류 매핑.
