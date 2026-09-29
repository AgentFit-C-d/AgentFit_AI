# 후보 기반 대표 기능 구성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 사용자가 직접 구현과 이번 목표의 자율 설계/계획/실행을 승인했다.

**Goal:**30개를 초과한 검토 후 기능 후보를 원문 대표로 구성하고 미포함 동작을 확인 필요로 보존한다.

**Architecture:** 새 helper가 대표/구성원 분할과 독립 포함 관계 검토를 수행한다. 기존 finalize는 선택형 feature_curation을 재검증하고 features의 투영만 제한한다. 기존 검토 상태와 다른 필드는 유지한다.

**Tech Stack:** Python, unittest, 기존 Solar/NVIDIA transport/JSON parser. 새 의존성 없음.

**Spec:** specs/ai-developer/04-analysis-provider/candidate-feature-curation/spec.md

## Global Constraints

- 공개 Profile·FastAPI·기본 분석기를 변경하지 않는다. 기본 feature_curation=None.
- 후보 최대240개, 문서100,000code point, 대표30개, 값200code point, 요청 출력8192토큰, 추가 호출0~2회. 자동 재시도 없음.
- 부정/미정/다른 필드/검토 탈락은 대표 구성에서 복구하지 않는다. 입력과 기존 검토 labels를 수정하지 않는다.
- 다른9개 필드의 값·근거·확인 필요를 유지한다. 미대표/미포함은 features 확인 필요다.
- 원문/키/응답/추론/Profile을 Git/안전 평가 산출물에 기록하지 않는다.
- 기능 브랜치 feature/candidate-feature-curation, 기반 a774923, 현재 isolated worktree 재사용.

## Review Focus

- 같은 표현의 서로 다른 확정/부정/미정 발생 위치: 확정 후보만 포함하며 Task1/2에서 ID·원문 근거를 검사한다.
- 모양이 유효하나 서로 다른 기능을 억지로 묶은 응답: Task1의 독립 검토가 uncovered ID를 남기고 Task2가 확인 필요를 유지한다. 의미 판단 자체는 Task3의 원문 대조 대상이다.
- 대표 누락과 원문 후보 누락의 혼동: Task2는 기존 검토 문제를 해제하지 않는다.
- 외부 응답의 허위 모델·절단·추가 ID와 두 번째 호출 실패: Task1에서 안전 실패와 호출 상한을 검사한다.
- 기존 non-feature 필드 및 관측 labels 변형: Task2에서 값/근거/상태와 deep copy를 비교한다.

## 실행 메모

동일 worktree의 GLM 스트리밍 임시 실험(PID2192, 셸14136)이 진행 중이다. 해당 세 코드 파일(candidate_split_review.py, deepseek_evaluation.py, candidate_field_semantics.py)은 이번 기능의 수정 대상이 아니다. 제품 코드 편집은 이 실험 종료와 기존 결과 기록 후 시작한다. 현재는 명세/계획 작성까지 진행한다.

### Task 1: 대표 분할·포함 관계 검증과 모델 요청

**Files:** Create ai_service/agentfit_ai/candidate_feature_curation.py, ai_service/tests/test_candidate_feature_curation.py.

**Interfaces:**
- Consumes: candidate_first_profile.validate_candidate_labels/_source_mention, candidate_split_review._payload, SolarAnalyzer/NvidiaAnalyzer의 검증된 _send_payload.
- Produces: `curate_reviewed_features(document, frozen, reviewed_labels, key, *, model='deepseek-ai/deepseek-v4.1-flash', transport=None, call_trace=None) -> dict | None`.
- Produces: `validate_feature_curation(document, frozen, reviewed_labels, curation) -> dict` with selectedIds/uncoveredIds/candidateCount. uncoveredIds는 미대표와 검토 미포함의 합집합을 입력 후보 순서로 반환한다.
- curation keys: groups/unrepresentedIds/checkedCandidateIds/uncoveredIds. group keys: representativeId/memberIds.

- [ ] **Step 1: 실패 테스트 작성.** `test_overflow_builds_partition_and_checks_every_member`에서31개 이상 합성 후보를 두 번 응답하는 transport로 입력하고 두 호출·전체 checked ID·원문 대표 선택을 확인한다. `test_no_overflow_uses_no_calls`는30개 이하/빈 목록에None·0호출. `test_invalid_partitions_fail_before_review`는 유실/중복/잘못된 ID/대표 비구성원/부정·다른 필드/31개 대표/빈 그룹/중복 값/201자 대표/잘못된 자료형을 확인한다. `test_invalid_review_and_provider_fail_closed`는checked 순서/중복/잘못된 uncovered·위장 모델·length·2차 실패를 확인한다. `test_unrepresented_and_uncovered_are_preserved`는분할 미대표와 검토 미포함의 합집합을 확인한다.
- [ ] **Step 2: RED.** Run `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_candidate_feature_curation.py -v` from ai_service. Expected: 새 모듈/인터페이스 없음으로 FAIL.
- [ ] **Step 3: 구현.** 문서/후보/옵션을 호출 전에 검사하고 검토 후 features/confirmed만 대상으로 사용한다. 고유 표현30개 초과 시 `_payload`로 두 엄격 스키마를 만들고 첫 분할을 검사한 뒤 두 번째 요청을 보낸다. 모델별 기존 전송/응답 검증을 재사용한다. 원문·raw를 제외한 허용 메타데이터만 call_trace에 남긴다.
- [ ] **Step 4: GREEN 및 커밋.** Step2 명령 Expected: PASS. 위 두 파일과 문서를 커밋한다. task-done도 같은 테스트 명령으로 기록한다.

### Task 2: 기존 Profile 투영에 선택적으로 연결

**Files:** Modify ai_service/agentfit_ai/candidate_first_profile.py; extend ai_service/tests/test_candidate_feature_curation.py.

**Interfaces:**
- Consumes: Task1 validate_feature_curation과 기존 finalize의 검토 후 safe_labels.
- Produces: `finalize_candidate_analysis(..., observer=None, feature_curation=None)`; None 결과 동일. opt-in 결과 `featureCuration={candidateCount,selectedCount,uncoveredCount}`만 추가한다.

- [ ] **Step 1: 실패 테스트 작성.** `test_projection_keeps_representatives_and_nine_fields`는31개 초과가 None 없이 대표 원문/정확 근거로 투영되고 다른9개 data/evidence가 기존과 같은지 검사한다. `test_projection_keeps_unresolved_and_reviewed_labels`는기존 wrong/missing/rejected 및 미대표/미포함이 확인 필요로 남고 observer reviewed labels와 입력이 변하지 않는지 검사한다. `test_projection_rejects_stale_or_foreign_curation`는현재 검토에서 탈락한 ID·다른 위치/부정 ID·잘못된 그룹을 거절한다. `test_default_projection_retains_existing_overflow_behavior`로선택 옵션 없는 결과 불변을 확인한다.
- [ ] **Step 2: RED.** Task1 명령 Expected: 새 keyword 없음으로 새 테스트 FAIL, 기존 Task1 PASS.
- [ ] **Step 3: 구현.** 내부 safe_labels를 유지하고 별도 projection_labels에서만 미선정 기능을 투영 대상에서 제외한다. groups 검증은 현재 document/frozen/safe_labels를 기준으로 다시 수행한다. uncovered 합집합이 있으면 features unresolved와 needs_confirmation, reviewIssueCount에해당 후보 수를 더한다. 기존 unresolved/완료 조건은 완화하지 않는다.
- [ ] **Step 4: GREEN 및 커밋.** Task1 명령 + 기존 candidate_first_profile/finalization 관련 테스트를 실행한다. Expected: PASS. 전체 단위 테스트 `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v`를 로그로 저장하고 종료/요약을 확인한다. Expected: 기존885개+새테스트, 기존6skip 외 실패0. task-done은 전체 명령으로 기록한다.

### Task 3: 실제 완료 스냅샷 평가·리뷰·push

**Files:** Add specs/.../candidate-feature-curation/validation.md, work/harness/candidate-feature-curation/STATE.md. 로컬 tmp에만 실제 평가 드라이버/안전 집계 파일.

**Interfaces:** Task1의 curate_reviewed_features, Task2의 optional finalize; restore_snapshot(case, completed_snapshot)의 원문/참조 검사.

- [ ] **Step 1: 사전 검증.** H02 완료 GLM 183개 snapshot을 복원하고 기존 verdict로 검토 후 labels를 수집한다. 기능41개 위치/37개 표현, 기존 features=null/array_limit, 원문 해시를 검증한다. 모델은 DeepSeek V4.1 Flash, 기존 adapter 설정, 추가 최대2호출이며 source/snapshot/code hash를 기록한다. Expected: 전송0회 preflight PASS.
- [ ] **Step 2: 실제 평가.** 새 결과 파일에서0~2회 curation 후 같은 verdict에 feature_curation을 적용한다. 원문/키/응답 전문 저장 금지. 후보ID 그룹·미포함ID·호출 진단·필드 집계·지정6개 검사와9필드 불변만 저장한다. Expected: 실행은 terminal/코드 불변으로 기록하고 품질은 관측값대로 보고한다. 유효 답변을 가정하지 않는다.
- [ ] **Step 3: 원문 대조.** 선택 대표와 모든 그룹을 로컬에서 대조해 독립 기능 누락/불필요 기대효과/부정/미정 혼입을 확인한다. 기존 후보 오류와 이번 선정 오류를 분리한다. 선별 정답으로 전체 정확도를 말하지 않는다.
- [ ] **Step 4: 독립 최종 코드 리뷰.** 전체 branch 범위/명세/계획/ledger/Review Focus를 새 리뷰어에게 전달한다. Important/Critical은 한번의 RED→GREEN 수정과 전체 테스트로 확인한다. 미검증 의미 품질/서비스 승격은 별도 남긴다.
- [ ] **Step 5: 기록·push·CI.** diff --check와 최종 변경 범위를 확인하고 기능 브랜치에 commit/push한다. 정확한 구현 커밋의 Linux CI 결과를 확인한다. 기본 서비스 승격은 실문서/반복/Spring 검증 완료 전 보류한다.

## Self-review

분할/두 단계 검토/호출 상한은Task1, 공개 투영·미확정/다른 필드 불변은Task2, 실문서 품질·진단·독립 리뷰·CI는Task3에 대응한다. 원문 근거의 존재와 대표 포함 관계의 의미 정확성을 구분한다. 별도 승인 요청은 이번 목표의 사용자 지시에 따라 생략하며 직접 구현한다.

## Task3 실제 실패 수정 순서

- 근거: 동일 설정 진단v2에서 분할 누락/중복0, 잘못된ID0, 중복 대표 표현1. 프롬프트와 모델 설정을 고정하고 서버 정규화만 변경한다.
- [ ] 중복 표현의 두 그룹을 역순으로 제공하는 회귀 테스트 작성: earliest supplied representative, 모든 구성원 보존, 독립 의미 검토 요청, 다른 문맥 미포함 유지, 입력 불변. 검토 실패 시 실패를 유지하고 미정규화된 최종 curation은 계속 거절한다.
- [ ] 관련 테스트 RED 확인 후 모델 제안 검증에만 중복 표현 허용; 나머지 분할 검증 유지. 그룹을 합치고 엄격 검증한 결과를 두 번째 요청에 보낸다. Expected: 새 테스트 GREEN, 기존12개와 전체 suite PASS.
- [ ] H02 v3는 같은 모델/프롬프트/입력으로 새 산출물에 최대2회 실행한다. v1/v2 실패를 지우지 않는다. 유효 그룹이 있으면 전체 후보의 포함 관계를 원문 대조한다.
- [ ] 독립 리뷰는5c37e99에서 결함 없음으로 종료됐다. 이번 실제 실패의 한정 수정은 위 RED→GREEN와 전체 suite/diff로 검증하고 범위를 validation에 구분한다. 최종 commit/push/정확한 CI를 확인한다.
