# 대표 기능 재구성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 이번 목표의 자율 실행 승인과 사용자 선택인 직접 순차 구현을 유지한다.

**Goal:** 미포함 기능이 있는 대표 그룹을 한 번 복구하고 전체 새 관계를 재검증한다.
**Architecture:** 기존 제안 코드를 공유 helper로 추출하고 재구성 helper가 이전 검토 자료로 재제안→엄격 정규화→새 관계 검토를 수행한다. 기존 curation 함수의 마지막에 한번 연결한다.
**Tech Stack:** Python/unittest/기존 Solar·NVIDIA adapters. 새 의존성 없음.
**Spec:** specs/ai-developer/04-analysis-provider/candidate-feature-regrouping/spec.md

## Global Constraints

- feature/candidate-feature-regrouping,base016c954,기존source-name-expressions worktree 재사용. 기본HTTP·공개Profile·다른9필드 불변.
- 문서100,000code point,후보240개,대표30개/200code point,출력8192,호출별timeout600초. 전체0~4호출,복구0~2호출,재시도0.
- 기존4키 curation,전체ID 분할,미포함/불확실 보존. 원문/키/응답 전문/추론은 저장하지 않는다.

## Review Focus

- 같은 배정을 다른 나열 순서로 돌려줘 불필요 재검토가 생기는 경우: Task1 동일배정 테스트.
- 초기 포함 관계가 새 대표에서는 미포함이 되는 경우: Task1 새 전체 검토·확인필요 테스트.
- 수정 분할의 같은 문구 다른 발생 위치: Task1 정규화와 새 쌍 검토 테스트.
- 초기0관계 분할에 미대표가 있는 경우: Task2 실제최대3호출 통합 테스트.
- 수정 실패를 숨기거나 반복하는 경우: Task1/2 제공자·잘못된구조·불확실·실패전달 테스트.

### Task 1: 단일 복구 helper

**Files:** Modify ai_service/agentfit_ai/candidate_feature_curation.py; create ai_service/agentfit_ai/candidate_feature_regrouping.py; create ai_service/tests/test_candidate_feature_regrouping.py.
**Interfaces:** `_propose_feature_partition(document,candidates,key,*,model,transport,call_trace,previous_curation=None)`는 엄격 정규화partition을 반환한다. `repair_feature_curation(document,frozen,reviewed_labels,curation,key,*,model=MODEL,transport=None,call_trace=None)->dict`는 기존4키를 반환하고 기존관계helper를소비한다.

- [ ] **Step1 tests:** 테스트명을수용행동에맞춘다. complete0call독립사본; unchanged순서변경1call; 새2그룹복구+전체쌍검토2calls/입력불변/원문범위; 이전covered가새uncovered로남고finalize확인필요; 동일값대표정규화후다른IDuncertain; 잘못된입력0call; 누락/중복/외부ID/대표31개/200초과/추가키의수정분할은1callFAIL; provider/model/length/관계구조실패는1~2callFAIL·safe진단.
- [ ] **Step2 RED:** ai_service에서 `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_candidate_feature_regrouping.py -v`. Expected: 새helper가없어FAIL.
- [ ] **Step3 implement:** 공유제안helper를추출하되기존첫요청불변. 복구입력검증→합집합정규화→필요시재제안→배정동일성비교→새관계전체검토. 데이터사본과예외전파. 아직curate에자동복구연결하지않는다.
- [ ] **Step4 GREEN/commit:** Step2및`-p test_candidate_feature_*.py` PASS. 커밋/task-done은관련전체명령.

### Task 2: 기존 선택형 흐름 연결

**Files:** Modify candidate_feature_curation.py,tests/test_candidate_feature_curation.py; extend tests/test_candidate_feature_regrouping.py.
**Interfaces:** Task1복구를curate의첫관계검토다음local import로1회호출. 시그니처/최종4키/기본None유지.

- [ ] **Step1 RED:** 통합테스트에서초기미포함→재구성→새검토의4호출과수정실패전파를확인. 기존singleton/반복대표/미대표테스트는재구성동일답을돌려1추가호출후기존확인필요유지. Expected: 기존함수가첫검토에서반환하여새배정·실패전파assertionFAIL.
- [ ] **Step2 implement:** 최초결과에단일복구연결. 최초정상완료는추가0회,동일수정은1회,변경수정은최대2회. 관계가없으면검토0회. 불확실을새복구로재귀호출하지않는다.
- [ ] **Step3 verify/commit:** 관련suite및전체`rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v`. Expected:기존6skip외실패0.커밋/task-done전체명령.

### Task 3: 고정 입력 실측·원문 감사·리뷰

**Files:** Create specs/.../candidate-feature-regrouping/validation.md; update work/harness/candidate-feature-regrouping/STATE.md. 평가driver/result는E:/AgentFit/tmp만.
**Interfaces:** 완료된candidate-feature-relations-h02-20260930-v2.json의두curation을Task1로수정한다. 기존finalize로투영비교.

- [ ] **Step1 preflight/live:** H02승인해시·snapshot183후보/41확정기능·완료v2·두curation전체검증·제품코드hash동결. Expected:0전송preflight PASS후각복구최대2회,총4회,명시종료. 새응답은ID/enum/안전개수만저장.
- [ ] **Step2 audit:** 새로운모든대표·비자기쌍을원문대조하고미포함변화/오포함/오거절/모호를구분. 원래36점수를새정답으로사용하지않는다. 다른9필드/labels보존. 품질판단은실측대로기록한다.
- [ ] **Step3 review/publish:** 전체branch에독립리뷰1회. Important/Critical만1회수정+회귀,재리뷰없음.실험중코드변경없음.기능push·정확한LinuxCI확인. 문서만남으면task-done은base016c954..HEAD diff --check.

## Self-review

3개task의partition/4키curation/호출상한이일치한다. 동일분할비교는배정의미로판단하므로순서변경만으로재검토하지않는다. 복구후악화도숨기지않으며원래완료기준을낮추지않는다. 자율설계·실행승인으로재승인을묻지않는다.
