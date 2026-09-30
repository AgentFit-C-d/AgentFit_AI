# 핵심 분석 흐름의 로컬 mock·계약 검증

## 목표와 권한

사용자가 실사용 범위를 입력→분석→사용자 확인·수정→Spring 저장으로 한정했다. Spring 저장소는 현재 제공할 수 없으므로 **현재 정의된 API 계약을 기준으로 mock 서버와 계약 테스트를 구현**하고 실제 Spring 연동은 미검증으로 남기라는 요청이다. 목표 안의 설계·계획·직접 구현은 재승인 없이 진행한다. SDD와 feature별 push를 유지한다.

외부 모델 호출 예산은 **0회/0원**이다. NVIDIA는 현재 계정에서 추가 요금이 없음을 확인한 엔드포인트만 별도 실험에 사용할 수 있고, 미확인/한도 소진 시 호출·재시도·유료 전환·충전·대체를 하지 않는다. 현재 기준선의 Solar 유료 사용은 승인되지 않았다. 개인 문서 외부 전송·운영 배포는 별도 승인 전까지 실행하지 않는다.

## 관측된 상태와 선택

- 기준선 코드 da49dfb와 문서·골드를 보존했다. 실제 평가1/30완료(ANALYSIS_FAILURE), 두 번째 요청은 비용 조건 변경으로 중단됐다. 종료 프로세스0개, 기존 결과를 재호출하지 않는다.
- AI는 confirmation-v2를 구현했지만 공개 API는 2026-09-08 계약이다. `Docs/api/analysis-confirmation-v1.draft.md`의 draftReview/질문 확인 확장은 합의 전 제안이다.
- 접근 가능한 GitHub 조직 저장소에는 AgentFit_AI만 있다. 실제 Spring/PostgreSQL/브라우저 검증은 여기서 증명할 수 없다.

선택지는 ①현재 공개 계약을 따르는 Python mock+실제 FastAPI 경계 테스트 ②Spring 대체 서버 구현 ③문서만 작성이다. **①을 선택**한다. 기존 공개 DTO와 오류·버전 동작을 실행 가능하게 보여 주고 후속 Spring 소비자 테스트에 재사용할 수 있다. 새 실제 백엔드나 DB를 만드는 범위는 포함하지 않는다.

## 구조와 격리

- `ai_service/contract_mock/`: 테스트 전용 메모리 저장소, 현재 OpenAPI 검증기, 공개 mock HTTP 서버, 합성 분석 연결.
- `ai_service/contract_tests/`: 소비자 관점 HTTP/스키마/경쟁/실패/삭제 테스트. 실제 모델·키·.env 접근이 없고 합성 문서만 사용한다.
- 기존 `agentfit_ai`와 production requirements는 수정하지 않는다. baseline frozen117/evaluator6 파일은 유지한다.
- 새 검증용 의존성 jsonschema4.26.0은 `contract_mock/requirements.txt`에 고정하고 프로젝트 전용 .venv에만 설치한다. 공개 OpenAPI 파일을 읽어 검증하며 별도 축약 스키마를 정답으로 만들지 않는다. `$ref`는 로컬 문서 내부만 허용한다.
- mock CLI는127.0.0.1만 bind하고 모델 호출 경로를 연결하지 않는다. 외부 AI URL/키 옵션이 없다. 로그에는 원문·응답·세션/토큰·예외 문자열을 쓰지 않는다.

## 현재 공개 계약

`Docs/api/common.md`, `01-project-analysis.md`, `openapi.phase1.json`을 기준으로 POST/GET projects, GET/DELETE project, POST analysis, PATCH profile을 제공한다. 성공·실패 모두 no-store와 서버 생성 request ID가 있다. mock 인증은 사전 등록된 합성 세션 쿠키만 사용하고 GitHub OAuth/실제 인증 구현으로 주장하지 않는다. 상태 변경은 설정된 단일 Origin과 일치해야 한다. 타인/없는 프로젝트는404로 동일하다.

- Project.version은0부터, 확인 저장 때만1 증가한다. DRAFT와 CONFIRMED는 별도다. 분석은 확인값을 덮어쓰지 않는다.
- PATCH는 expectedVersion와 전체10개 data, 선택적인 draftId/draftVersion 쌍만 허용한다. 현재 공개 계약에 없는 acknowledgedQuestionIds를 조용히 추가하지 않는다.
- null→UNKNOWN/근거[]; 기준과 같은 알려진 값→기존 출처·근거 유지; 변경된 알려진 값→USER/근거[]. []와null을 구별한다. null이 남아도 저장 가능하다.
- Project/초안 버전 검사와 저장은 메모리 저장소의 같은 잠금 안에서 처리한다. 동시에 같은 버전으로 저장하면 정확히1개만 성공하고 나머지는409다. 저장 실패 주입 시 기존 상태와 버전이 바뀌지 않는다.
- 분석 응답과 상세 응답은 현재 OpenAPI의 키를 그대로 사용한다. **공개 draftReview/질문 재조회 형식은 아직 없다.** v2 질문은 AI 경계에서 검증하고 mock 내부에서 초안과 연결하되 공개 DTO를 임의 확장하지 않는다. 현재 공개 계약으로 v2 질문 재조회/명시적 질문 확인 UI까지 완료했다고 주장하지 않는다. 필요한 확장은 별도 인계 문서에 기록한다.

## 입력·분석·실패·중복

- PDF/Markdown/TEXT raw 입력을 기존 FastAPI 어댑터로 전달한다. 실제 문서 파서와 HTTP 응답 검증을 사용하고 모델 생성은 합성 callback으로 대체한다. 분석 내용의 정확도는 이 테스트의 대상이 아니다.
- mock에서 UTF8/JSON/추가 키,10MiB raw·64KiB JSON, 문서 유형·Origin/세션·소유권을 검사한다. 거부 시 모델 호출0회다.
- 동일 프로젝트 동시 분석409, 사용자 진행1개/서버2개 초과429. 완료/실패/timeout/취소 후 슬롯 반환. 자동 POST/PATCH 재전송0회, 명시적 재입력만 새 분석을 시작한다.
- needs_confirmation은 검증된 DRAFT·Attempt 저장 후에만 성공 응답을 준다. AI의200 failed는 공개502 AI_UNAVAILABLE로 매핑하고 기존 DRAFT/CONFIRMED를 보존한다. invalid 결과는502 AI_INVALID_OUTPUT, timeout은504 ANALYSIS_TIMEOUT, 저장 장애는503 STORAGE_UNAVAILABLE이다.
- 분석이 끝나기 전에 프로젝트가 삭제되면 지연 결과가 프로젝트·초안을 복원하지 않는다. 삭제된 프로젝트의 진단 자료도 다시 쓰지 않는다.
- 응답 유실 뒤 GET은 실제 mock 저장 상태를 반환한다. 같은 expectedVersion PATCH 재전송은409이며 자동 덮어쓰지 않는다.

## 보관·삭제의 mock 정책

요청 원문과 추출문은 mock 저장소에 저장하지 않는다. 공개 Profile의 값·근거 위치 및 최소 문서/Attempt 정보만 유지한다. Audit는 ID·고정 사건명·결과·시각만 허용한다.

실패 응답 보관은 **합성 진단 입력을 주입하는 테스트 경로**로만 모의한다. 실패한 기존 Attempt에 대해 최대7일 보관, 성공 건 저장 금지, 정확한7일 경계에서 삭제, 프로젝트 삭제와 함께 제거, 삭제 후 지연 기록 금지를 검증한다. 공개 endpoint·일반 로그에 진단 원문을 내보내지 않는다. 실제 AI→Spring 진단 전송·권한·DB/백업/운영 로그 삭제는 별도 미검증 항목이다.

## 검증과 완료 증거

1. 실제 OpenAPI 스키마로 요청/응답을 검사한다. 추가 키/잘못된 타입/빈 문자열/null·[]/출처·근거의 변화와 버전 충돌을 검사한다.
2. 합성 TEXT/Markdown/PDF 각각 공개 mock→실제 FastAPI 추출·확인 응답→초안→수정 PATCH→GET의 흐름을 검사한다.
3. AI 실패/시간 초과/잘못된 v2·질문/저장 실패/동시 요청/중복 PATCH/응답 유실/삭제 경쟁을 재현한다.
4. 예외·문서·민감 sentinel이 로그/공개 오류/저장 원문에 남지 않음을 검사하고7일 만료·프로젝트 삭제를 가상 시계로 검사한다.
5. 자동 테스트, localhost 실제 TCP 테스트, 미실행 실제 Spring/PostgreSQL/브라우저/운영 검증을 구분한다. 실제 청구·모델 품질을 mock 결과로 추정하지 않는다.
6. 명세·계획·검증/인계 문서, feature/core-analysis-contract-tests push와 정확한CI, 최종 독립 코드리뷰1회가 기능 완료 기준이다. 핵심 흐름 전체의 실사용 달성을 뜻하지 않는다.

## 실행 상한

| 작업 | 작업 시간 점검 상한 | 테스트 실행 상한 | 자동 재시도 | 모델 호출/유료 예산 |
|---|---:|---:|---:|---:|
| 계약 검증기·메모리 저장소 |45분 후 범위 재점검|각180초|0|0회/0원|
| HTTP 연결·실패/경쟁 처리 |60분 후 범위 재점검|각180초, mock 분석 기본2초|0|0회/0원|
| 삭제·로그·인계·전체 검증 |45분 후 범위 재점검|각180초, CI job15분|0|0회/0원|

원인별 수정이3회 실패하면 조사 결과를 정리하고 구조/가정을 재검토한다. 시간 상한에 도달하면 실제 경과와 남은 일을 기록해 계획을 갱신하며 완료 기준을 낮추지 않는다. 외부 유료 재시도로 문제를 숨기지 않는다.
