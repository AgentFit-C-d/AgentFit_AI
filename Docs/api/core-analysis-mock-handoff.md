# 핵심 분석 흐름 — 로컬 mock과 Spring 연결 인계

2026-09-30. **현재 API 계약의 시험 도구이며 실제 Spring 구현·운영 검증 결과가 아니다.**

## 실행과 범위

저장소 루트의 프로젝트 전용 Python 환경을 사용한다. 설치와 실행 예시:

```powershell
rtk proxy .venv/Scripts/python.exe -m pip install -r ai_service/contract_mock/requirements.txt
# 작업 디렉터리: ai_service
rtk proxy ../.venv/Scripts/python.exe -m contract_mock
```

127.0.0.1:8765에만 바인딩한다. 종료하면 메모리 데이터가 사라진다. `.env`, 실제 API 키, 외부 AI URL 설정은 사용하지 않는다. 기본 분석기는 합성 문장 `MockPlan uses React.`만 인식한다. TEXT·Markdown·PDF는 기존 FastAPI의 실제 파서와 v2 응답 검증을 거친다. 이 결과로 실제 기획서 분석 정확도를 판단할 수 없다.

모든 응답은 `X-AgentFit-Mock: true`, `Cache-Control: no-store`, 서버 생성 `X-Request-Id`를 포함한다. 인증은 **합성 세션** `better-auth.session_token=mock-session-a` 또는 `mock-session-b`다. OAuth·실제 세션 DB 검증을 구현하지 않는다. 변경 요청에는 `Origin: http://127.0.0.1:8765`가 필요하다. URL과 세션을 운영용으로 사용하지 않는다.

## 요청·응답 연결

정확한 모든 필드·nullable·추가 키 금지는 [현재 OpenAPI](openapi.phase1.json), 업무 규칙은 [프로젝트 API](01-project-analysis.md)를 따른다.

| 요청 | 입력 | 성공 응답 |
| --- | --- | --- |
| POST `/api/projects` | JSON `{ "name": "Mock plan" }` | 201 `{ project }`, version 0 |
| GET `/api/projects` | 본문 없음 | 200 `{ projects }`, 본인만 |
| POST `/api/projects/{id}/analysis` | raw UTF-8 TEXT/Markdown 또는 PDF bytes | 200 `{ draft, attempt }`, **초안 저장 이후** |
| PATCH `/api/projects/{id}/profile` | 전체 data + expectedVersion + 선택 draftId/draftVersion 쌍 | 200 `{ project, confirmed }`, Project.version +1 |
| GET `/api/projects/{id}` | 본문 없음 | 200 `{ project, confirmed, draft, latestAttempt }` |
| DELETE `/api/projects/{id}` | JSON `{ "confirmation": true }` | 204, 본문 없음 |

분석 Content-Type: `text/plain`, `text/markdown`, `application/pdf`. raw 최대10MiB, 추출 텍스트 최대100,000자, PDF 최대100쪽. JSON 최대65,536bytes. 파일 표시 이름은 선택 `X-Document-Name`에 UTF-8 URI encoding으로 전달한다. 잘못된 encoding·제어문자·경로·200자 초과를 거절한다. TEXT에는 파일 이름을 보내지 않는다.

초안을 수정한 확인 저장의 합성 예시(실제 응답의 ID·버전 사용):

```json
{
  "expectedVersion": 0,
  "draftId": "prof_example",
  "draftVersion": 1,
  "data": {
    "project_name": "MockPlan",
    "project_type": null,
    "domain": null,
    "frontend": ["Vue"],
    "backend": null,
    "ai": [],
    "database": null,
    "deployment": null,
    "features": null,
    "external_integrations": null
  }
}
```

null은 미정, []는 명시적 없음이다. 기준 초안과 같은 알려진 값은 DOCUMENT 근거를 유지한다. 바꾼 값은 USER/근거[], null은 UNKNOWN/근거[]다. sources/evidence/unknownFields/kind는 서버가 만들며 입력으로 받지 않는다. DRAFT와 CONFIRMED는 별도로 보관한다.

## AI 내부 경계

mock은 실제 AI 앱을 **ASGI 메모리 통신**으로 호출한다. 실제 Spring HTTP 연결은 아직 없다.

```text
POST /internal/v1/analyze
Authorization: Bearer <서비스 내부 토큰>
X-AgentFit-Analysis-Contract: confirmation-v2
X-Document-Kind: TEXT | MARKDOWN | PDF
X-Document-Id: <서버 생성 문서 ID>
X-Request-Id: <서버 생성 요청 ID>
Content-Type: <공개 raw 입력과 같은 유형>
```

실제 토큰을 문서·클라이언트·로그에 넣지 않는다. mock의 `mock-internal`은 합성 테스트 값이다. v2 결과의 정확한 상태·질문 규칙은 [v2 인계 초안](analysis-confirmation-v2.draft.md)을 참조한다. AI의 200만으로 공개 저장 성공을 반환하지 않는다. Profile·질문·requestId·documentId·근거 형식을 검증한 뒤 DRAFT/Attempt를 저장한다. TEXT는 알려진 문자 수에 대한 근거 끝 범위도 검사한다. PDF의 원문 근거 검증은 실제 AI 파서/검증기에 의존하며 mock이 독립적으로 재추출하지 않는다.

## 실패·재시도·동시성

오류 본문은 항상 `{ "error": { "code": "...", "message": "안전한 안내", "requestId": "..." } }`다.

| 상황 | 공개 상태/코드 | 다음 처리 |
| --- | --- | --- |
| 인증/Origin/소유권 | 401/403/404 | 입력 검사보다 먼저 거절; 타인/없는 ID 동일404 |
| 같은 프로젝트 분석 중 | 409 ANALYSIS_BUSY | 진행 상태 재조회 |
| 사용자1건/서버2건 초과 | 429 RATE_LIMITED, Retry-After: 1 | 자동 POST 재전송 없음 |
| AI 200 failed | 502 AI_UNAVAILABLE | 이전 draft/confirmed 보존 |
| v2 응답/질문/ID/근거 오류 | 502 AI_INVALID_OUTPUT | 새 draft 저장 금지 |
| 전체 기한 초과 | 504 ANALYSIS_TIMEOUT | Attempt 실패, 재입력으로만 재시도 |
| 저장 장애 | 503 STORAGE_UNAVAILABLE | 기존 값·버전 보존 |
| Project/draft 버전 충돌 | 409 VERSION_CONFLICT | 편집값 보존, GET 후 사용자 재검토 |
| 입력 유형/크기/내용 오류 | 415/413/422 | 안전한 코드, 원문 오류 문자열 제외 |

mock 전체 분석 기한은2초, 생성자에서0초 초과60초 이하로 시험할 수 있다. 실제 운영60초/후속 실험예산은 별도 합의해야 한다. 업로드 전에 슬롯을 확보하고 실패·취소·timeout에 반환한다. 프로젝트가 삭제돼도 진행 중 요청의 실제 슬롯은 종료될 때까지 유지한다. 늦은 완료가 삭제 데이터를 복원할 수 없다. 만료된 PROCESSING은 조회/새 요청/완료 시 INTERRUPTED로 정리한다.

TCP 끊김은 Attempt를 INTERRUPTED로 정리하고 대기 중인 합성 AI 작업을 취소한다. 실제 모델 프로세스·네트워크의 중단 전파는 이 mock 결과로 증명하지 않는다. 이미 커밋된 PATCH 응답이 사라지면 GET으로 실제 상태를 복구한다. 같은 expectedVersion 재전송은409이며 새 버전 자동 덮어쓰기·자동 재분석이 없다.

## 개인정보·삭제 검증 범위

- 제출 원문/추출문/예외 원문은 저장하지 않는다. Profile 값과 근거 위치, 최소 문서·Attempt·ID/고정 사건명/시각 Audit만 남긴다.
- 저장할 이름·Profile·파일 이름에는 식별 가능한 credential 라벨/개인키 패턴 거절을 적용한다. 완전한 민감정보 탐지나 모든 PDF 내용의 비밀 탐지를 보장하지 않는다. 실제 서비스는 별도 검증이 필요하다.
- 실패 진단은 **테스트 전용 합성 bytes 주입**으로만 시험한다. 실패 완료 Attempt만 허용하고 실패 시각+7일이 상한이다. 뒤늦은 기록이나 덮어쓰기로 만료를 연장하지 않는다. 조회/수집 공개 API가 없다.
- `purge_diagnostics()`와 만료 후 count/기록 경로를 시험한다. 프로젝트 삭제는 해당 진단도 제거하고 삭제 후 늦은 기록을 거절한다. 운영 스케줄러·DB 물리 삭제·백업 삭제는 구현/검증하지 않았다.
- HTTP access log는 CLI에서 끈다. 합성 sentinel 테스트는 공개 오류·메모리 저장소·캡처 로그의 누출을 검사한다. 운영 호스트/프록시/Provider 로그는 미검증이다.

## 실제 Spring 연결 때 통과해야 할 항목

별도의 `core_flow_tests`로 아래 로컬 연결을 함께 검증한다. **현재 범위는 합성 TEXT·Markdown·PDF 입력과 메모리 저장이며 실제 Spring은 포함하지 않는다.**

```text
공개 TCP 요청 → mock → ASGI FastAPI → 실제 분석 자식 프로세스
             → 실제 LangExtract/분석기 → loopback 합성 HTTP/SSE 응답
             → v2 근거 검증 → DRAFT → 사용자 수정 PATCH → CONFIRMED → 재조회
```

전용 환경에 기존 통합·mock 의존성을 설치한 뒤 `ai_service/`에서 실행한다.

```text
python -m pip install -r requirements-integrated.txt -r contract_mock/requirements.txt
python -m pip check
python -m unittest discover -s core_flow_tests -v
```

실제 분석기의 10개 필드와 non-null unresolved가 초안에 보존되고, 수동 수정의 null/[] 및 출처, 재조회·중복 버전409·삭제를 검사한다. 손상된 합성 Provider 응답은 이전 초안/확인본을 유지하며 명시적 재시도로만 복구한다. 공개 연결 종료와 mock의 기한 만료가 실제 자식 프로세스와 합성 Provider socket을 종료하는지도 검사한다. 기본 mock callback을 실모델로 교체하거나 외부 연결을 허용하는 실행 옵션은 추가하지 않았다.

검증 결과는 [핵심 흐름 runtime 기록](../../specs/ai-developer/core-flow-runtime-checks/validation.md)을 따른다. CI의 `core-flow-runtime` job은 이 suite를 별도로 실행한다. 실제 외부 Provider, 질문별 명시적 확인 UI, Spring/DB 및 운영 환경의 검증은 아래 목록에 남긴다.

`integrated-nvidia` 선택형 서비스도 실제 child·LangExtract·합성 NVIDIA SSE를 거쳐 동일 mock 저장 계약에 연결했다. 단독 경로는 Solar 키 없이 실행하며 429/503에서 자동재시도하지 않는다. 단독 API의 전체 기한/TCP 종료/ASGI 취소 시 프로세스·socket 정리, mock의 초안·확인본 보존·명시적 재요청·중복409·삭제를 별도로 검증한다. 상세 결과는 [NVIDIA 단독 연결 기록](../../specs/ai-developer/nvidia-analysis-service/validation.md)에 있다. 합성 TEXT/메모리 저장 범위이며 실제 Spring·운영 저장·실제 모델 품질 검증을 대신하지 않는다.

2026-10-01 추가: [문서 입력 통합 검증](../../specs/ai-developer/document-input-runtime/validation.md)은 NVIDIA 단독 합성 경로에서 BOM·한글·이모지·CRLF Markdown과 두 페이지 PDF의 실제 파싱, 근거 위치, 수정 저장·재조회·버전 충돌·삭제를 검사한다. 잘못된 문서 8종은 추가 모델 호출 없이 거절하며 기존 저장본을 보존한다. PDF의 `pageCount`·`characterCount`는 현행 내부 응답에 전달되지 않아 mock에서는 **null**이다. 실제 OCR·복잡한 PDF 레이아웃 품질이나 Spring 저장 검증은 추가되지 않았다.

- [ ] Spring이 이 요청·응답 OpenAPI와 오류/우선순위를 그대로 구현하는지 소비자 테스트 실행
- [ ] 실제 인증 쿠키·세션 만료·Origin·소유권·다른 프로젝트 draft 접근 검증
- [ ] Spring→FastAPI 실제 HTTP 토큰·헤더·ID·timeout·크기·오류 매핑 검증
- [ ] v2 질문 저장/재조회/명시적 사용자 확인의 공개 계약 합의 및 구현
- [ ] PostgreSQL 트랜잭션에서 expectedVersion·draftVersion 비교와 저장/Audit가 원자적인지 경쟁 시험
- [ ] DB 장애/재시작/응답 유실/연결 취소/중복/삭제와 늦은 완료를 실제 환경에서 재현
- [ ] 브라우저가 편집값을 보존하고 자동 재전송 없이 충돌·재접속을 처리하는지 확인
- [ ] 실패 원본 진단의 실제 전달 경로·접근 권한·7일 삭제 작업·삭제 cascade·백업/운영 로그 점검
- [ ] 비용 없는 모델 계정/엔드포인트 확인 후 고정 평가 재개 여부 결정; 임시 골드는 사람이 검토

미확인 NVIDIA 무료 상태에서는 실제 모델 호출0회다. 무료 한도 소진 시 유료 전환·충전·대체·재시도를 하지 않는다. 이번 mock 검증은 모델 품질 평가 완료, 실제 Spring 저장 완료, 전체 실사용 목표 달성을 뜻하지 않는다.
