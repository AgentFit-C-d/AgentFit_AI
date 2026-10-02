# 문서 입력부터 Profile까지 평가 준비 계획

> **For agentic workers:** 향후 구현이 승인되면 `superpowers:executing-plans`로 직접 순서대로 수행한다. **현재 요청은 계획까지만이며 아래 구현·모델 호출은 실행하지 않는다.**

**Goal:** 실제 AgentFit 기획서의 10개 필드와 세부 의미가 어느 단계에서 누락되거나 잘못 확정되는지 판별하는 평가를 준비한다.

**Architecture:** 로컬 평가 진입점은 실제 문서 파서와 현재 NVIDIA 후보 분석 함수, 최종 확인 응답 생성·검증 함수를 그대로 호출한다. 평가 전용 관측으로 단계 결과를 저장하고, 별도 채점 단계에서만 정답과 대조한다. HTTP와 자식 프로세스 경계의 동등성은 합성 응답을 사용하는 별도 로컬 계약 검증으로 구분한다.

**Tech Stack:** 기존 Python, LangExtract 1.7.0, unittest, httpx, FastAPI. 추가 의존성 설치 없음.

**Spec:** [spec.md](spec.md), [expected-values-draft.md](expected-values-draft.md).

## 공통 제한

- 지금은 모델 호출 0회·앱 코드 변경 0건. 목표 중단 상태와 기존 비교 결과를 유지한다.
- 정답·원문·32개 또는 68개 등의 과거 후보를 추출 입력에 주입하지 않는다. 단위 ID 평가 기준선과 기존 모델 비교 자료는 그대로 보존한다.
- 특정 이름 예외 처리, 새 관계 검증기, 새 모델 단계, 분류 프롬프트 수정, 서비스 적용을 포함하지 않는다.
- 긍정 필수 요구와 구현 완료를 구분한다. 30개 이하 대표 기능으로 표현하되 세부 의미 36개의 보존을 따로 측정한다.
- 단계 기록은 평가 출력 디렉터리에만 저장한다. API 키·인증 헤더·개인 환경 설정을 저장하지 않는다. 운영 원문 보관 정책을 바꾸지 않는다.

## 현재 코드에서 확인한 경로

| 구간 | 확인한 파일·동작 | 관측 한계 |
| --- | --- | --- |
| API 입력 | `ai_service/agentfit_ai/http_service.py:create_app`, `/internal/v1/analyze`, `extract_document` | 배포 설정 미확인. 코드 기본 모드는 `default` |
| 자식 분석 | `analysis_worker.py:execute_request`는 `integrated-nvidia`에서 `semantic_assessment=True` 지정 | 호출 진단 외 상세 단계 observer를 worker가 현재 노출하지 않음 |
| 후보 생성·분류 | `candidate_analysis_pipeline.py:analyze_nvidia_candidates` → LangExtract와 동작 후보 추출 → 근거 연결·병합 → 의미 분류 | `grounded`, `classified` 관측 가능. 원시 추출·병합 전후 상세 기록은 추가 필요 |
| 검토·대표 기능·Profile | `candidate_first_profile.py:finalize_candidate_analysis` | `reviewed`, `projected` 관측 가능. 대표 기능의 selected/covered/uncovered 대응표는 현재 요약 수치만 최종 반환 |
| 최종 확인 응답 | `candidate_service_worker.py` → `project_candidate_confirmation`; HTTP는 `validate_candidate_confirmation` 재검증 | 최종 Profile만 보면 후보 손실 단계를 판단할 수 없음 |

이 평가의 직접 함수 경로는 모델 품질·중간 원인을 상세히 보기 위한 로컬 분석 평가다. **실제 HTTP+자식 프로세스로 같은 문서를 실제 모델에 보낸 결과와 동일하다고 주장하지 않는다.** 후자의 동등성은 아래 합성 계약 검사에서 별도 보고하며, 운영 설정·Spring 저장은 미검증으로 둔다.

## 정답 및 측정표

평가 파일 `gold-draft.json`은 검토 후 버전을 고정한다. 실제 호출 결과를 보고 기존 정답을 수정하면 새 평가 버전으로 분리하며 해당 실행의 원래 점수도 보존한다.

| 지표 | 분모·계수 규칙 |
| --- | --- |
| 필드 상태 | 10개. `stated/unknown/explicit_none`의 범위를 평가. 이 문서의 필드 전체 explicit_none은 0이므로 해당 유형 성능은 평가 불가 |
| 정상 정보 | 기능 외 4개 사실 + 기능 세부 의미 36개 = 40개. 추가 문구나 광범위한 제목만으로 충족 판정하지 않음 |
| 추출 누락 | 40개 중 원시 일반·동작 추출 모두에 의미상 대응 항목이 없는 수. 파싱 실패·추출 호출 미완료는 별도 미평가 |
| 위치 연결·병합 손실 | 원시 추출에 대응 항목이 있는데 유효 병합 후보에 없는 수와 이유 |
| 분류 오류 | 대응 후보가 관측된 항목 중 잘못된 필드/범위/시점/부정/확정성. 복수 원인이면 최초 오류와 보조 원인을 각각 기록 |
| 모델 오확정 | 골드 밖 또는 골드의 미정·부정·다른 대상인 후보를 모델이 긍정 확정한 수. 후보 발생 건수와 의미상 고유 주장 수 모두 보고 |
| 서버 통과 오확정 | 최종 Profile의 긍정 값에 남은 잘못된 고유 주장 수. `needs_confirmation` 응답 안의 잘못된 제안도 포함 |
| 후처리 누락 | 올바르게 분류된 의미가 검토→기능 요약→Profile→확인 응답 중 사라진 수. 대표 항목이 같은 의미를 보존하면 누락 아님 |
| 최종 정상 누락 | 40개 중 최종 긍정 Profile에 없는 수. 이 중 확인 자료로만 보존된 수와 완전히 사라진 수를 분리 |
| 보류 | 알려진 긍정 사실의 과도한 보류, 미정 항목의 적절한 보류, 후보는 있었으나 확인 자료에서도 유실된 수를 각각 보고 |
| 부정·범위 판정 | 골드의 16개 문맥 점검 항목 각각: 추출 여부, 적절한 부정/범위 밖/보류, 잘못된 확정. 안 뽑힌 항목은 분류 정답으로 자동 계산하지 않음 |
| 인용 결함 | 원문 불일치, 잘못된 등장 위치, 다른 대상·범위를 지지하는 인용 선택을 분리. 의미는 맞아도 근거 위치가 틀리면 별도 결함 |
| 확인 부담 | 최종 질문 수, 고유 확인 대상 의미 수, 그중 골드 긍정 40개에 관한 수. 정상적인 사용자 승인 질문과 AI 불확실성 해결 질문을 분리 |
| 시간·호출 | 실제 provider 요청마다 단계·모델·성공/실패·경과 시간. 문서 파싱부터 최종 응답까지 총 경과 시간과 관측 기록 비용 |

골드 의미와 후보의 대응은 **인용 위치+내용+대상/범위**를 함께 읽어 작성한다. 한 단어만 같거나 ID가 같다는 이유로 매칭하지 않는다. 새로운 표현의 의미가 애매하면 `human_review`로 두고 확정 점수와 미판정 수를 함께 보고한다. 모델을 채점자로 추가 호출하지 않는다.

원인 장부는 의미 단위별 `firstMismatchStage` 하나와 모든 단계의 `present/correct/held/missing/unobserved`를 보존한다. 누락을 세 단계에 중복 가산하지 않는다. 중간 오류가 복구됐다면 최초 오류와 `recovered=true`를 함께 남긴다. 최종 누락은 별도 결과 지표이므로 최초 원인 지표와 합산하지 않는다. ‘후보 없음’과 ‘단계 기록 없음’은 구분한다.

## Review Focus

1. 문서 해시는 같아도 CRLF를 LF로 바꾸면 Unicode 위치가 달라질 수 있다 → 과제 2에서 바이트/텍스트 경계 검사.
2. 넓은 대표 기능 하나가 구체적 기능 여러 개를 숨길 수 있다 → 과제 3에서 요약 보존과 실제 유실의 대조 검사.
3. 미구현 필수 요구를 일괄 미래 계획으로 제외할 수 있다 → 과제 1의 범위 고정, 과제 3의 분류 오류 장부 검사.
4. `null` 설명 근거를 공개 Profile evidence로 넣거나 명시적 제외 하나로 배열 전체를 비울 수 있다 → 과제 2·3에서 계약/범위 검사.
5. API 오류·trace 유실을 누락 0건 또는 완전 성공으로 처리할 수 있다 → 과제 2·3에서 불완전 실행 중단 및 미관측 검사.

## 과제 1 — 기대값 검토·동결 (다음 단계의 선행 조건)

**파일:** 현재 디렉터리의 `gold-draft.json`, `expected-values-draft.md`, `expected-profile-draft.json`.

**입출력:** 사용자 검토 전 초안 → 검토된 골드의 버전·해시·수정 사유. 골드는 채점기에만 전달한다.

- [ ] 10개 필드와 16개 기능 묶음/36개 의미 단위의 포함 범위를 사용자와 검토한다. domain 표현과 기능 묶음의 의미는 확정 전 초안임을 유지한다.
- [ ] 선택 확장·첫 기능 제외·평가 후보의 시점/범위를 고정한다. 범위가 애매한 의미는 주 점수에서 제외하고 별도 표에 남긴다.
- [ ] 문서·정답·코드 해시와 모델을 보지 않은 판정 규칙을 동결한다. 이번 준비에서는 초안을 승인 완료로 바꾸지 않는다.

## 과제 2 — 문서 입력 및 중간 결과 관측 (향후 로컬 구현)

**파일:**
- 생성: `ai_service/agentfit_ai/document_profile_evaluation.py` — 문서 입력·오프라인 기본 모드·평가 결과 묶음.
- 수정: `ai_service/agentfit_ai/candidate_analysis_pipeline.py`, `candidate_first_profile.py` — 기존 `observer`가 있을 때만 관측 항목 보강. 판정 로직 변경 금지.
- 생성: `ai_service/tests/test_document_profile_evaluation.py`.

**인터페이스:** `prepare_document(source: Path) -> dict`는 바이트/추출문 해시와 파서 결과를 반환. `capture_stage(stage: str, payload: dict) -> None`은 평가 전용 기록기로 사용. `run_document_evaluation(source: Path, output: Path, *, execute: bool = False) -> dict`는 `execute=False`에서 파싱·동결 검사까지만 수행하며 API 키를 읽거나 모델 transport를 만들지 않는다. 이 함수에 골드·후보 파일 인자는 없다.

- [ ] 네트워크 차단 상태에서 원문 CRLF·Unicode 위치 보존, 기본 모드 모델 호출 0회, 저장 후보 주입 인터페이스 부재의 실패 테스트를 먼저 작성한다.
- [ ] `rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m unittest discover -s tests -p test_document_profile_evaluation.py -v`를 `ai_service`에서 실행해 새 요구의 실패를 확인한다.
- [ ] 실제 `extract_document('MARKDOWN', raw)` → `analyze_nvidia_candidates(..., semantic_assessment=True)` → `project_candidate_confirmation` → `validate_candidate_confirmation` 호출을 연결한다. 코드의 기존 기본 모델·프롬프트·서버 판정을 사용하고 이전 U/US 비교 분류기는 삽입하지 않는다.
- [ ] 관측 단계 `general_extracted`, `general_grounded`, `operations_extracted`, `grounded`, `classified`, `reviewed`, `feature_curated`, `projected`, `final_response`를 연결한다. 일반 원시 응답, 근거 연결 거절 이유, 동작 후보, 분류 modelDecisions, 기능 대표 선정의 전체 매핑을 누락 없이 저장한다. 동작 추출에서 raw 응답과 결과가 다르면 provider 응답 기록과 연결한다.
- [ ] 같은 합성 provider 응답으로 관측 켜짐/꺼짐의 반환 값·요청 순서·호출 수가 동일한지 검사한다. 기존 공개 응답에 trace를 추가하지 않는다.
- [ ] 같은 합성 문서·응답으로 실제 `/internal/v1/analyze` + 자식 프로세스 경로와 평가 함수 경로의 최종 결과를 비교한다. 기존 `core_flow_tests/test_document_input_runtime.py`의 루프백 provider 관례를 재사용하되 저장·배포 검증으로 확대하지 않는다. `requestId/documentId`만 정규화하고 필드·근거·판정은 그대로 비교한다.
- [ ] 위 로컬 검사와 `test_candidate_analysis_pipeline.py`, `test_candidate_confirmation.py`를 실행하고 결과를 기록한다. 준비/관측 변경만 별도 커밋한다.

## 과제 3 — 최초 오류 귀속·최종 지표 (향후 로컬 구현)

**파일:**
- 생성: `ai_service/agentfit_ai/document_profile_scoring.py`, `ai_service/tests/test_document_profile_scoring.py`.
- 생성(실행 산출물): `output/document-profile-evaluation/<run-id>/alignment.json`, `stage-ledger.json`, `metrics.json`, `report.md`.

**인터페이스:** `score_document_trace(trace: dict, gold: dict, alignment: list[dict]) -> dict`. `alignment`는 골드 의미 ID, 새 후보 ID/원문 위치, 의미 매칭 판정, 근거, human_review 여부를 기록한다. 채점 모듈은 모델 호출 함수·키를 사용하지 않는다.

- [ ] 원시 추출 누락 / grounding 손실 / 오분류 / 검토 손실 / 의미를 보존한 기능 통합 / 통합 중 의미 유실 / 응답 유실을 각각 한 건씩 심은 합성 trace로 최초 단계와 최종 누락의 기대 수를 고정한다.
- [ ] 정상 필수 요구, 선택 사항 보류, 범위가 있는 명시적 부정, 사용자 승인 질문, 분류가 애매한 새로운 요약, trace 미관측을 포함한다. 서비스 이름 예외 규칙을 만들지 않는다.
- [ ] `rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m unittest discover -s tests -p test_document_profile_scoring.py -v`로 실패 확인 후 최소 구현한다.
- [ ] 모델 오확정과 최종 Profile 오확정, 정상 누락과 후보 유실, 적정/과도 보류, 질문 수가 서로 독립적으로 나오는지 검증한다. 기존 후보가 하나도 없으면 분류 정확도는 100%가 아닌 평가 불가다.
- [ ] 모델 결과를 보지 않은 정답·동결 항목을 변경하지 않은 채 로컬 합성 검사 결과를 기록하고 커밋한다. 이 결과를 실제 모델 품질로 보고하지 않는다.

## 과제 4 — 후속 실행 요청을 받았을 때만 실제 평가

- [ ] 사용자 검토를 통과한 골드와 테스트를 먼저 확인한다. 현재 자료는 `draft_pending_user_review`이므로 실행 게이트를 통과하지 않는다.
- [ ] 당시 무료 이용이 확인되는 모델·엔드포인트, 전체 호출 수·시간 상한을 제시하고 해당 평가의 실행 권한을 확인한다. 코드의 `max_calls=64`는 구현 상한일 뿐 사용 승인량이 아니다. 재시도 0회·첫 실패 중단·유료 대체 금지를 유지한다.
- [ ] 원문 하나로 새 추출부터 끝까지 한 실행을 수행한다. 단계별 모델, 모든 요청 지침·스키마·문맥 범위, 응답과 bounded transport 진단, 전체 시간을 보존한다. 실패하면 완료된 단계만 보고하고 후속 호출하지 않는다.
- [ ] 위 측정표로 수치와 실제 오류 사례를 보고한다. 수정 전후 비교는 이번 실행을 기준선으로 저장한 뒤 별도 승인한 후속 변경에서만 한다. 기존 후보 주입 실험의 숫자와 직접 성능 비교하지 않는다.
- [ ] 보고 후 종료한다. 서비스 적용·Spring 연동·큰 goal 재개는 하지 않는다.

## 이번 준비 결과와 자체 검토

- [x] 원문 1개 선택, 해시 고정, 10개 필드의 기대값과 16개 기능 묶음/36개 의미 단위 작성.
- [x] 명시적 부정과 선택 사항의 범위 및 원문 인용 기록. 필드 전체 명시적 없음 사례가 없다는 한계 명시.
- [x] 추출·분류·후처리 및 위치 연결 손실의 분모와 최초 단계 규칙 작성.
- [x] 원문 인용 98곳과 기존 Profile 형식 검증. 실제 모델·서비스 경로 실행은 미실행.
- [x] spec 요구를 과제 1–4에 대응했고, 인터페이스의 골드 분리와 관측 한계·네트워크 기본 차단·문서 사용 이력을 자체 검토함.
- [ ] 기대값 사용자 검토, 평가 도구 구현, 로컬 합성 실행 검증, 실제 모델 평가 — **다음 승인 이후 작업**.
