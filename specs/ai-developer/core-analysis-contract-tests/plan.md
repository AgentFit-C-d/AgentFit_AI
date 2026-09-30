# 핵심 분석 mock·계약 테스트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자가 선택한 직접 순차 구현과 목표 내 자율 설계·구현 권한을 유지한다. 구현 에이전트를 위임하지 않는다.

**Goal:** 현재 공개 API의 입력→분석 초안→전체 필드 확인·수정→저장·재조회 계약과 실패 경계를 비용 없는 mock으로 실행한다.
**Architecture:** 현재 OpenAPI 검증기→잠금이 있는 메모리 mock 저장소→공개 FastAPI mock→합성 생성 callback을 쓰는 기존 AI FastAPI. 실제 모델·키·.env·PostgreSQL은 연결하지 않는다.
**Tech Stack:** Python3.13, 기존FastAPI/httpx/unittest, jsonschema4.26.0(테스트용 선택 의존성).
**Spec:** specs/ai-developer/core-analysis-contract-tests/spec.md

## Global Constraints

- 브랜치feature/core-analysis-contract-tests, base23c3235, 기존 isolated analysis-runtime 재사용. production agentfit_ai117/evaluator6과 production requirements/공개 OpenAPI는 수정하지 않는다.
- 외부 모델 호출0회/0원, 외부 AI endpoint/키 옵션 없음. 합성 문서만 사용하고 민감 입력·응답·예외 문자열을 로그에 넣지 않는다.
- 요청/응답은현재OpenAPI; v2 draftReview나 acknowledgedQuestionIds를 공개계약에 임의 추가하지 않는다. 공개 질문 재조회 공백은 인계 문서에서 명시한다.
- 각 작업 시간점검45/60/45분, 테스트명령180초, 자동재시도0. 실패 수정3회는 원인/설계 재점검. CI job15분. 작업 시간이 넘으면 실제 경과와 남은 일을 기록한다.
- 실제Spring/인증/PostgreSQL/브라우저/운영보관·삭제는 미검증이다. mock 정상 동작을 모델 품질·사람 검토·실서비스 성공으로 승격하지 않는다.

## Review Focus

1. 동시 확인/새 초안/삭제와 늦은 분석 완료가 기존 확인값을 덮어쓰거나 삭제 데이터를 복원하지 않는가(Task2 경쟁 테스트).
2. null·[]·직접 작성·수정 후 값 복원·다른 프로젝트 draft가 출처/근거/버전 검증을 우회하지 않는가(Task1 의미 회귀).
3. 실제공개Schema의 제약을 mock이 자기규칙으로 완화하거나 v2 질문 계약 공백을 숨기지 않는가(Task1/3 스키마·인계검증).
4. 취소/timeout/저장 실패가 슬롯·PROCESSING·편집값을 유실시키거나 원문을 저장하지 않는가(Task2/3 실패 주입).
5. 실패진단의7일 경계·성공 시 저장금지·삭제후지연쓰기·로그의민감값이 mock통과를 운영보장으로 보이게 하지 않는가(Task3 보관/로그테스트).

### Task 1: 현재 계약 검증기와 확인 저장 mock

**Files:** contract_mock/__init__.py, requirements.txt, schema.py, store.py; contract_tests/test_mock_store.py (모두 ai_service 아래). Docs/api/openapi.phase1.json은 읽기 전용이다.
**Interfaces:**
- `schema.check(name: str, value: object)->None`: 실제 components.schemas의 JSON Schema로 검증, 실패는 내용 없는 `ContractError(status:int, code:str)`. 요청은CreateProjectRequest/DeleteProjectRequest/SaveProfileRequest, 응답은ProjectListResponse/CreateProjectResponse/ProjectDetailResponse/AnalysisResponse/SaveProfileResponse/ErrorEnvelope. 로컬 $ref만 허용; name allowlist. 공백문자열/잘못된 정수 타입 등 의미조건은 저장소가 보완한다.
- `MockStore(clock: Callable[[],datetime]|None=None)`; `create(owner:str,name:str)->dict`, `list(owner)->dict`, `detail(owner,project_id)->dict`, `save(owner,project_id,payload)->dict`, `delete(owner,project_id)->None`.
- Task2가 사용할 `begin(owner,project_id,document:dict)->dict`(Attempt), `finish(owner,project_id,attempt_id,profile:dict,review:dict)->dict`(AnalysisResponse), `fail(owner,project_id,attempt_id,error_code:str)->None`. begin은같은프로젝트409,같은사용자1/전체2초과429; finish/fail은currentattempt와존재를대조. `fail_next_write:bool`는합성장애1회주입으로외부HTTP옵션없음.
- 저장 상태는 딥카피로만 반환하며 UTC시각/UUID합성ID를 서버가 만든다. Project0,Profile1부터; confirmed와draft별도버전. finish에서저장하는 review는내부전용, 공개응답에는추가키없음. expectedVersion/draft쌍 검사·update·Audit는동일RLock.

- [x] Step1: `test_mock_store.py`를먼저작성. create→manualsave→GET일치, 같은known/변경known/null/[]의출처·근거, staleexpected/draft·crossproject404, 누락/추가키422, 두스레드동일버전exactly1success/1conflict, 저장장애시완전불변, DRAFT/CONFIRMED별도, 반환객체변형격리. 모든응답은실제OpenAPI로검증.
- [x] Step2: cwdai_service에서 `python -m unittest discover -s contract_tests -p test_mock_store.py -v` 실행. Expected:새contract_mock API미구현으로RED. missingcontract_mock 확인.
- [x] Step3: 별도선택의존성파일에 `-r ../requirements-dev.txt` 및 `jsonschema[format-nongpl]==4.26.0`을고정한다. 프로젝트.venv에만설치후check/schema/store를최소구현. 오류에 jsonschema exception문자열포함금지, invalidvalidation은고정코드만. GREEN9/9, pipcheck충돌0.
- [x] Step4: 같은테스트GREEN과 기존tests전체회귀. Expected: 모든응답schema유효, 버전원자성·출처보존·누출방지검증. 797b113 및 task-done 전체게이트 통과.

### Task 2: 실제 AI HTTP 경계에 연결한 공개 mock

**Files:** contract_mock/server.py, gateway.py, __main__.py; contract_tests/test_mock_http.py, test_mock_analysis_lifecycle.py.
**Interfaces:**
- `create_mock_app(*, store=None, ai_app=None, sessions=None, origin='http://127.0.0.1:8765', analysis_timeout_seconds=2)->FastAPI`. sessions기본은합성쿠키토큰2개→mock사용자2명. Cookie이름better-auth.session_token, Origin정확일치, nosto re/requestID middleware, bodymaxraw10485760/JSON65536.
- `LocalAnalysisGateway(ai_app)`의 `async analyze(kind,body,document_id,request_id)->dict`: httpx.ASGITransport로기존AI앱호출만가능, baseURL은합성local도메인, trust_env=False, retries0. Bearer는합성내부토큰, contract=confirmation-v2, 기존rawContent-Type. HTTP실패코드를현재공개ErrorEnvelope로명시매핑.
- 기본 ai_app은 `agentfit_ai.http_service.create_app`에합성분석callback을주입한다. callback은고정MockPlan/React등의합성fixture만인식하고타문서는안전실패를반환한다. 실제production파서·v2validator를그대로거친다. 외부모델코드호출금지.
- `python -m contract_mock`는uvicorn127.0.0.1:8765,access_log=False,합성세션/고정Origin만사용. 서비스는mock표시를응답header `X-AgentFit-Mock: true`로추가하되JSON스키마는보존한다.

- [x] Step1: HTTP기반RED: TEXT/Markdown/PDF→DRAFT→editedPATCH→GET, 인증/Origin/소유권우선순위, 불법body/큰body/메타데이터추가키거절, 전체JSONSchema, v2unresolved nonnull·질문누락/변조거절, publicdraftReview미제공을명시검사.
- [x] Step2: gateway/server/CLI구현. 입력헤더/상태/정수와유효UTC는실제계약. 성공상태는mock저장후에만반환,일반로그는고정사건ID/코드만. Gateway는키/.env/외부URL읽기없음.
- [x] Step3: 경쟁RED: 동일프로젝트진행중409,같은사용자다른프로젝트429,전체2개초과429,AI200failed→502기존초안유지,timeout→504후재시도가능,취소후Attempt정리,delete중지연완료시복원금지,동시PATCH409,응답유실뒤GET/중복PATCH충돌. 주입callback에는 asyncio.Event/모의clock를사용하고실제대기1초이하.
- [x] Step4: 원인별최소구현후 `python -m unittest discover -s contract_tests -v`, 기존전체tests/runtime_tests. precommit1117/5skip44.106초,runtime11/11 38.434초,contract23/23 2.876초 통과. commit/task-done 기록은 ledger에 남긴다.

### Task 3: 삭제·로그·실제 TCP 검증과 Spring 인계

**Files:** contract_mock/store.py, contract_tests/test_mock_privacy.py, test_mock_tcp.py; Docs/api/analysis-confirmation-v2.draft.md, Docs/api/core-analysis-mock-handoff.md, Docs/api/README.md; specfolder validation.md; .github/workflows/ai-linux.yml; work/harness/core-analysis-contract-tests/STATE.md.
**Interfaces:** `MockStore.record_failed_diagnostic(owner,project_id,attempt_id,payload:bytes)->None`, `purge_diagnostics()->int`(명시clock), `diagnostic_count()->int`. mock단위테스트의합성데이터용이며공개원문전송API아님. 실패완료Attempt만허용,7일정확경계·프로젝트삭제·삭제후지연쓰기차단. 메모리진단조회 endpoint없음.

- [x] Step1: RED→GREEN: 성공건진단기록거절,7일직전유지/경계삭제,다른프로젝트진단보존,delete후진단재작성금지,제출원문sentinel이저장/Audit/로그/공개오류에없음,예외메시지민감값차단,저장실패기존확인값보존.
- [x] Step2: localhost실제TCP서버+합성AI로1개핵심흐름과삭제를검증. 외부connect를차단한실행환경에서재현하고테스트후서버종료확인. 공개examples/요청응답/errorcode와Spring/DB연결검증체크리스트를작성; v2질문재조회/확인신호/진단전송은미합의·미구현으로표시.
- Step3: 기존Linuxworkflow에contract-mock job추가,별도requirements설치,pipcheck,contract_tests실행(job15분). Frozenproduction117/evaluator6해시를재확인. 전체unit/runtime/contract테스트,최종독립코드리뷰1회(Critical/Important만1수정pass),featurepush/exactCI. Expected:mock검증완료·실제Spring未검증이명확한인계. 전체실사용목표는미완료유지.
  - 로컬구현/전체gate/리뷰1회수정 완료: unit1117/5skip,runtime11/11,contract36/36. 실행 상세는validation.md와review.md.
  - 최종push의 정확한HEAD/CI 결과는SDD ledger와최종보고에서 확인한다. 별도재리뷰·merge·배포를하지않는다.

## 설계·계획 검토

새서비스대체/모델변경없이기존계약을실행하는시험도구로범위를정했다. 공개질문메타데이터와실제진단전송은현재계약에없어완료대상으로위장하지않는다. 각ReviewFocus는위실패테스트로연결했다. 사용자의자율설계·직접구현승인을적용해재승인을묻지않는다. JSONSchema사용법은[공식검증API](https://python-jsonschema.readthedocs.io/en/stable/validate/)를따른다.
