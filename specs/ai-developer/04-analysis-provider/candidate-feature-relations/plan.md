# 후보 쌍별 포함 관계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 선택인 직접 순차 구현과 이번 목표의 자율 설계·계획·실행을 유지한다.

**Goal:** 대표 자신에 대한 모순을 제거하고 서로 다른 후보의 포함 관계를 명시적으로 검토한다.
**Architecture:** 새 helper가 엄격 분할로 쌍을 만들고0~1회 관계 평가 후 기존 curation으로 합성한다. 기존 curated flow의 두 번째 요청을 대체하고 최종 검증에도 자기 모순 거절을 추가한다.
**Tech Stack:** Python/unittest/기존Solar·NVIDIA adapters. 새 의존성 없음.
**Spec:** specs/ai-developer/04-analysis-provider/candidate-feature-relations/spec.md

## Global Constraints

- 공개Profile·HTTP·기본 분석기 불변. feature/candidate-feature-relations,base9b583c4,기존worktree재사용.
- 문서100,000code point,후보240개,대표30개/200code point,출력8192,timeout600초. 검토0~1호출·전체구성0~2호출·자동재시도0.
- 응답assessments의memberId/representativeId/coverage 외 자유 문자열 없음. 불확실은미포함.
- 입력/근거/다른9필드/기존 확인 필요 보존. 원문·키·응답 전문·Profile은Git/진단에 기록하지 않는다.

## Review Focus

- 같은 문구의 다른 문맥을 자기 포함으로 오인: Task1에서 다른ID는 쌍 생성/uncertain 유지.
- 모델이 그럴듯한 다른 대표에 붙여 반환: Task1에서 정확한pair와전체배정 검증.
- 판단할 관계가 없어 검토를 생략할 때 미대표 소실: Task1의0호출/확인필요 테스트.
- 최종API에 자기 미포함 모순을 직접 주입: Task2의 final validator 거절 테스트.
- 코드테스트만으로 품질개선 선언: Task3의 고정분할36판정·2모호별도·기존판정과비교.

### Task 1: 쌍 검토 helper

**Files:** Create ai_service/agentfit_ai/candidate_feature_relations.py, ai_service/tests/test_candidate_feature_relations.py.
**Interfaces:** Consumes _feature_candidates/_validate_partition/validate_feature_curation and existing adapters. Produces `review_feature_relations(document,frozen,reviewed_labels,partition,key,*,model=MODEL,transport=None,call_trace=None)->dict` (기존4키 curation).

- [x] **Step1 tests:** `test_relations_only_review_nonself_members`는합성31후보·서로다른대표/구성원에서정확쌍/원문/선별후보/원순서결과/입력불변/1호출을확인. `test_server_only_partition_uses_no_calls`는30대표+미대표1개에서0호출·미포함보존. `test_identical_text_at_distinct_positions_is_reviewed`는같은값다른ID의uncertain이확인필요로남음. `test_invalid_assessments_fail_closed`는누락/중복/외부ID/다른대표/자기쌍/미대표쌍/자료형/enum/추가키. `test_invalid_input_does_not_call_provider`는검토전분할/옵션/문서오류. `test_provider_errors_and_diagnostics`는모델위장/length/실패 및원문/키비노출.
- [x] **Step2 RED:** ai_service에서 `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_candidate_feature_relations.py -v`. Expected: 새helper없음FAIL.
- [x] **Step3 implement:** 분할엄격검사→입력순서비자기쌍→0호출또는1회schema요청→정확전체쌍검증→기존curation합성·최종검증. 반환사본/안전진단. 순서자유응답을서버순서로정규화한다.
- [x] **Step4 GREEN/commit:** Step2명령PASS후커밋. task-done도해당명령.

### Task 2: 대표 구성 연결과 최종 불변식

**Files:** Modify candidate_feature_curation.py, tests/test_candidate_feature_curation.py; extend test_candidate_feature_relations.py.
**Interfaces:** Task1 helper를정규화된partition에서호출. curate_reviewed_features시그니처불변/최대2호출. validate_feature_curation의기존반환불변.

- [x] **Step1 RED tests:** 기존coverage canned reply를쌍별응답으로마이그레이션하고통합테스트가새요청/0관계생략/두번째실패를검사. 새 `test_final_curation_rejects_self_uncovered`는기존validator가자기ID미포함을거절해야함. Expected: 기존전체coverage요청과자기모순허용으로FAIL.
- [x] **Step2 implement:** curate의두번째요청을Task1로교체(local import로순환방지). 최종validator는대표∩uncovered를거절한다. 기존그룹선택/정규화/오류상태는유지.
- [x] **Step3 GREEN:** 두관련파일테스트PASS후전체 `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v` 실행. Expected: 기존6skip외실패0. 커밋/task-done전체명령.

### Task 3: 고정 분할 실측·리뷰·push

**Files:** specs/.../candidate-feature-relations/validation.md,work/harness/candidate-feature-relations/STATE.md. 실제driver/result는로컬tmp만.
**Interfaces:** 두완료curation에서partition만복원하고Task1을직접호출한다. 기존finalize로다른9필드/상태불변확인.

- [x] **Step1 preflight:** 승인H02해시/완료GLM183후보/검토후41기능/두완료결과code_unchanged/전체partition검증. 관계6/32와사전36판정/2모호를확인. Expected:0전송PASS.
- [x] **Step2 live:** DeepSeek기존설정으로각고정분할1호출. 원문/키/응답전문저장없이개수·ID·coverage enum·종료/시간/hash만기록. Expected:종료상태검증,품질은관측대로. unknown/uncertain/구조실패구분.
- [x] **Step3 audit:** 지정판정일치/보류/오판과2모호를원문대조. 제안선정문제와검토문제분리. 개선이없어도전체목표유지.
- [x] **Step4 review:** 전체branch/spec/plan/ledger/ReviewFocus를독립최종리뷰1회. Important/Critical은1회RED→GREEN수정+전체suite,재리뷰없음.
- [x] **Step5 publish:** 기록·diff --check·commit/push·정확한구현LinuxCI확인. 기본서비스승격미실시. task-done은전체branch diff --check(문서만남은경우코드suite재실행하지않음).

## Self-review

계약/모델실패는Task1,연결/자기모순/기본경로는Task2,실측과일반화제한은Task3에대응한다. helper이름/인수/4키결과가세Task에서일치한다. 기존승인은유지하고재승인을묻지않는다.

## Task3 관측에 따른 프롬프트 한정 수정

v1의 명확한 관계 오포함7개가 추가 문맥 규칙v2에서0개로 줄고 지정36개 중34개 일치했다. 별칭6/6 유지,모호2개 제외,새 미포함 오판2개는 남는다. 제품 프롬프트에 실험과 동일한 일반 문맥 규칙을 추가한다. 문구 존재를 반복하는 단위 테스트는 만들지 않는다. 사전 고정된 실제v1/v2의 오포함 판정으로 실패→개선 근거를 기록하고, 메모리 캡처 transport로 기존 프롬프트+실험 추가문구와 제품 요청 전체가 두 분할에서 정확히 같은지 확인한다. 외부 호출0회이며 원문 요청은 파일에 저장하지 않는다. 전체907개 회귀를 재실행하고 정확한 수정 커밋을push/CI확인한다. 독립리뷰58c8e52 이후의 이 한정 변경 범위를 별도 기록한다.
