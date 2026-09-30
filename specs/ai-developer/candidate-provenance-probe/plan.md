# 후보 단계별 누락 진단 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The user selected direct implementation and authorized autonomous goal planning and execution. Steps use checkbox syntax.

**Goal:** 실제 기능 누락의 최초 경계를 원문·응답 추가 저장 없이 관찰한다.

**Architecture:** 평가 전용 관측기와 worker가 기존 분석 함수의 observer 및 부모의 command 주입 경계를 재사용한다. 프로덕션 분석 모듈은 수정하지 않고, 별도 runner가 원래 freeze와 진단 도구 해시를 함께 검증한다.

**Tech Stack:** 기존 Python·unittest·asyncio·LangExtract/NVIDIA 런타임. 신규 의존성 없음.

**Spec:** `specs/ai-developer/candidate-provenance-probe/spec.md`

## Global Constraints

- 현재 session72538의 30회 기준선 평가가 종료된 후 구현한다. 기존 결과·gold·freeze를 보존한다.
- `feature/candidate-provenance-probe`, 직접 구현, 기능별 commit/push. merge·PR·배포·삭제 없음.
- 모든 새 실행 코드는 `ai_service/diagnostic_tools/`에 둔다. `agentfit_ai` 소스·기본 서비스 패킷·공개 Profile은 유지한다.
- 키·원문·값·원본 응답·예외 문자열을 진단에 기록하지 않는다. gold는 부모 사후 분석에서만 사용한다.
- 후보 최대240, 문자열 값 상한200코드포인트, 대표 기능 최대30, 진단 JSON 최대2MiB. 상태 enum은 confirmed/negated/tentative/irrelevant.
- 기본 진단 stages는 grounded/classified/reviewed/projected. 미관측은 null이다.
- 구현/로컬 검증 외부 모델0·유료0·재시도0. 로컬 그룹당180초, 구현90분마다 증거 재검토.
- 실제 진단은 PUBLIC-01/PUBLIC-09/PUBLIC-07 각1회, DeepSeek 전 단계, 요청1800초/64호출, 합계192호출/90분, 재시도0. 무료 범위·만료·예산을 매 요청 전 검증한다.
- PowerShell의 모든 셸 명령은 rtk로 실행하고 명시한 파일만 stage한다. 기존 `.superpowers` 자료를 보존한다.

## Review Focus

1. 반복·중첩·긴 인용: 위치가 겹친다는 사실을 의미 정답이나 검토 오류로 단정하지 않는지 확인한다. Task1의 반복 위치·길이 경계 테스트에 포함한다.
2. 기능 정리 실패와 미관측 reviewed: 이미 수행된 모델 검토를 관측되지 않았다는 이유로 누락 단계로 판정하지 않는지 확인한다. Task1/2의 중도 실패 테스트에 포함한다.
3. 진단 파일 충돌·부분 파일·경로 링크: 기존 자료가 덮어써지거나 미완료 파일이 성공으로 수락되지 않는지 확인한다. Task2/3의 경로·중단 테스트에 포함한다.
4. 관측기 오류·악성 상태·API 키 같은 문자열: 정상 결과를 바꾸거나 원문을 오류로 내보내지 않는지 확인한다. Task1/2의 불변성·비노출 테스트에 포함한다.
5. 도구 코드 변경·무료 범위 만료·제공자 오류: 자료가 섞이거나 다음 호출/재시도가 발생하지 않는지 확인한다. Task3의 freeze·예산·중단 테스트에 포함한다.

## 실행 전 순서

1. session72538 종료와 저장 결과 감사를 마친다. 현재 feature의 보고 문서만 commit/push한다.
2. 새 feature 브랜치 생성 후 이 명세·계획을 commit한다. SDD workspace/ledger를 생성하고 기존 worktree 격리를 확인한다.
3. Task1→Task2→Task3을 직접 구현한다. 각 task의 RED→GREEN과 task-done 증거를 기록한다.
4. 최종 전체 검증 후 가장 적합한 모델의 독립 최종 리뷰 1회. 구현 에이전트·재리뷰 없이 중요한 지적만 회귀 테스트로 수정한다.
5. push·CI 후 별도 새 결과 폴더에서 제한된 실제 진단을 수행한다. 결과와 다음 수정 판단을 기록한다.

### Task 1: 원문을 보관하지 않는 후보 관측기

**Files:**
- Create: `ai_service/diagnostic_tools/__init__.py`
- Create: `ai_service/diagnostic_tools/candidate_trace.py`
- Test: `ai_service/tests/test_candidate_trace.py`

**Interfaces:**
- Consumes: 기존 observer의 `(stage: str, state: dict)`와 최종 candidate 분석 결과.
- Produces: `CandidateTrace(document: str, document_id: str)`, `.observe(stage, state) -> None`, `.finish(result: dict) -> None`, `.summary() -> dict`; `validate_trace(document: str, document_id: str, value: dict) -> dict`.

- [ ] **Step 1: 관측기 실패 테스트 작성.** `test_stage_labels_locate_exclusion`에서 같은 후보가 grounded에 있고 classified에서confirmed, reviewed에서irrelevant로 바뀐 기록을 확인한다. `test_long_value_explains_projection_hold`에서 201자 후보와 짧은 후보가 같은 features에 있고 최종null이 된 이유에 필요한 ID·개수를 확인한다. `test_repeated_positions_stay_distinct`는 같은 문구의 위치 두 개를 병합하지 않는다. `test_missing_stage_is_none`은 중도 종료가 false/0 성공으로 바뀌지 않는다. `test_trace_rejects_invalid_shapes_and_never_emits_values`는 bool 위치·범위 초과·중복ID·임의필드/상태·역순단계·초과후보·임의키를 거절하고 document/값을 summary에서 찾을 수 없음을 확인한다.
- [ ] **Step 2: RED 실행.** `rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m unittest discover -s tests -p test_candidate_trace.py -v` (cwd ai_service). Expected: 신규 모듈/구현 부재로 실패.
- [ ] **Step 3: 순수 관측·엄격 검증 구현.** 고정 키·enum·정수만 직렬화한다. 필드별 값 개수는 null/빈 배열을 구분하고, 후보별 길이·위치는 소스에서 검증한다. 복사된 자료를 반환해 호출자가 내부 상태를 바꾸지 못하게 한다. 올바른 위치·필드 도달과 의미 정답은 구분한다.
- [ ] **Step 4: GREEN 실행.** Step2 명령. Expected: 모든 신규 테스트 통과, 외부 호출0.
- [ ] **Step 5: 해당 소스·테스트만 commit 후 같은 명령으로 task-done.** Expected: commit 생성 및 ledger의 검증된 완료 기록.

### Task 2: 기존 worker 결과를 유지하는 격리 진단

**Files:**
- Create: `ai_service/diagnostic_tools/candidate_trace_worker.py`
- Test: `ai_service/tests/test_candidate_trace_worker.py`
- Test: `ai_service/runtime_tests/test_candidate_trace_runtime.py`
- Create test-only shim under `ai_service/runtime_tests/` if existing local Provider helper needs a launch adapter.

**Interfaces:**
- Consumes: Task1의 CandidateTrace/validate_trace, 기존 `analysis_worker.execute_request(raw)`와 `candidate_service_worker.analyze_nvidia_candidates`.
- Produces: `execute_probe_request(raw: bytes, trace_path: Path) -> bytes`, `validate_probe_report(document: str, document_id: str, value: dict) -> dict`, `python -m diagnostic_tools.candidate_trace_worker TRACE_PATH`.

- [ ] **Step 1: 실패 테스트 작성.** 동일한 합성 제공자 응답에서 원래 worker와 진단 worker의 응답/요청 payload/호출 수가 같다. 관측 오류는 sidecar를 invalid로 표시하고 원래 응답을 유지한다. wrapper는 finally에서 복구한다. 출력 경로가 존재하거나 링크이면 모델 호출 전에 거절하고 기존 파일을 보존한다. provider failure 이전까지 관측된 단계만 남기고 이후는 null이다. trace/stdout/argv/env에 문서·키·응답·예외 문자열이 진단으로 유출되지 않는다(기존 stdin/정상 Profile 응답은 기존 계약대로 처리).
- [ ] **Step 2: RED 실행.** `rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m unittest discover -s tests -p test_candidate_trace_worker.py -v`. Expected: 신규 worker 부재로 실패. 런타임 RED는 `-s runtime_tests -p test_candidate_trace_runtime.py -v`로 실행한다.
- [ ] **Step 3: worker 구현.** 진단 파일을 독점 생성한 후 기존 worker를 실행한다. 격리 프로세스 안에서만 분석 호출을 감싸 observer를 넣는다. 관측 오류는 고정 코드로 격리하며 모델 재호출을 하지 않는다. 완전한 JSON만 flush/fsync하고 부모가 검증한다. 기록 실패/중단 자료는 성공 진단으로 취급하지 않는다.
- [ ] **Step 4: GREEN 실행.** Step2 두 명령. Expected: unit 및 실제 자식/로컬 SSE 제공자 비교 통과. timeout과 cancel에서 자식·소켓이 종료되고 incomplete trace는 수락되지 않는다. 실제 외부 API 호출0.
- [ ] **Step 5: 해당 파일만 commit 후 두 그룹을 실행하는 제한된 검증 helper로 task-done.** Expected: 두 그룹 모두 통과 및 ledger 완료 기록.

### Task 3: 고정 자료의 3문서 진단 실행기

**Files:**
- Create: `ai_service/diagnostic_tools/candidate_trace_probe.py`
- Test: `ai_service/tests/test_candidate_trace_probe.py`
- Documentation: 현재 spec의 `validation.md`, `live-plan.md`, `result.md`.

**Interfaces:**
- Consumes: Task2의 worker command와 validate_probe_report(내부적으로 Task1의 validate_trace 호출); 기존 `prepare_evaluation`, `validate_free_access`, `load_nvidia_key`, `run_scored_process`, `_diagnostic_row`, `_write_new`.
- Produces: `prepare_probe(corpus_file, gold_file, freeze_file) -> dict`; `async run_probe(prepared, output, nvidia_key, access_file) -> dict`; `main(argv=None)`.

- [ ] **Step 1: 실패 테스트 작성.** 기본 CLI는 로컬 준비만 실행하고 키를 읽지 않는다. --live에서만 원래 env loader를 호출한다. 세 case를 고정 순서로 각1회 실행하고 timeout1800/호출64/재시도0을 유지한다. 원래 freeze에 더해 모든 diagnostic_tools 소스 해시를 manifest에 기록하고 요청 전/후 검증한다. 기존 output·started-only·부분 trace·다른 source identity·도구 해시 변경은 재실행/수락하지 않는다. 무료 만료·범위오류·예산초과는 모델 호출 전 중단하고, provider error 후 다음 case가 실행되지 않는다. 모델에 gold가 전달되지 않는다.
- [ ] **Step 2: RED 실행.** `rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m unittest discover -s tests -p test_candidate_trace_probe.py -v`. Expected: 신규 runner 부재로 실패.
- [ ] **Step 3: 제한된 runner 구현.** manifest는 baseline metadata와 자체 source hashes를 분리 저장한다. 부모가 받은 기존 score/call diagnostics와 검증된 sidecar를 요청별 새 파일로 묶는다. 출력은 개수·고정 상태·위치·hash만 사용하고 오류 문자열은 고정 코드만 출력한다. 사람 검토와 release gate는 false로 유지한다.
- [ ] **Step 4: GREEN과 회귀 실행.** Step2, 신규 진단 unit/runtime 전체 및 기존 unit/runtime/contract/core 그룹을 각각180초 이내에 실행한다. Expected: 전체 통과, 기존 플랫폼 skip만 별도 기록, 실제 API0.
- [ ] **Step 5: 소스·테스트·검증 문서 commit 후 task-done.** Expected: 실행 증거를 포함한 ledger 완료 기록. 독립 최종 리뷰→push/CI까지 확인 후 실제 진단 단계로 이동한다.

## 자체 검토

요구사항은 관측 계약(Task1), 기존 결과 불변·격리(Task2), provenance/비용/중단(Task3)으로 배정했다. Task2는 Task1 summary만 소비하고 Task3은 엄격 검증 후 수락한다. 공개 API를 추가하지 않으며 새로운 품질 점수를 만들지 않는다. live 평가의 성공과 구현 테스트 통과는 별도로 보고한다.
