# 기능 관계 회귀 평가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 승인된 직접 순차 구현과 자율 SDD를 유지한다.

**Goal:** 제품 관계 검토의 의미 정확성과 순서·반복 안정성을 고정 합성12사례로 측정한다.
**Architecture:** 고정코퍼스→정확위치후보준비→두순서·반복별기존helper호출→안전한행집계→CLI진행보고서. 제품분석기동작은바꾸지않는다.
**Tech Stack:** Python/unittest/기존NVIDIAadapter. 새의존성없음.
**Spec:** specs/ai-developer/04-analysis-provider/feature-relation-regression/spec.md

## Global Constraints

- feature/feature-relation-regression,base7c87d6a. 기존worktree재사용. H02새근거감사는승인대기로유지.
- 창작12사례(포함5/미포함7),기본2순서×2회=48호출. 최대24사례×2순서×3회=144. 1회600초/8192토큰/재시도0.공개Profile/기본서비스불변.
- 정답미전송,실문서문구미사용,보고서에키/원문/인용/응답전문없음. 실패/불확실을성공으로세지않는다.

## Review Focus

- 같은인용두번에서잘못된발생위치선택: Task1원문반복위치테스트.
- 기존분류정답을모델성능으로오인: Task1부정/검토후보요청제외·범위명시.
- 실패끼리같아일관성성공으로집계: Task1실패/불확실/순서·반복집계테스트.
- 보고서쓰기실패후유료호출계속: Task2checkpoint오류전파테스트.
- 기존결과/코퍼스변경/잘못된repeats로무의미실호출: Task1입력검증,Task2CLI사전검증/배타생성테스트.

### Task 1: 코퍼스와 평가 runner

**Files:** Create specs/.../feature-relation-regression/cases.json,ai_service/agentfit_ai/feature_relation_evaluation.py,ai_service/tests/test_feature_relation_evaluation.py.
**Interfaces:** prepare_case(case)->dict(document,frozen,labels,partition,id,expected); load_cases(path,expected_sha256)->list; evaluate_cases(cases,key,*,model=MODEL,repeats=2,transport=None,checkpoint=None)->dict. checkpoint는안전집계dict를받는다.

- [ ] **Step1 tests/data:** 직접작성12사례/정답(5positive7negative)을모델호출전에고정. 반복인용occurrence를다른위치에고정,오류/중복/허용상한거절. 실제helper+전송fake로2순서×2회=4요청/정답미전송/irrelevant후보제외. literal판정배열로matched3/4,오거절1,순서일치1/2·반복일치1/2. 실패/uncertain도계획분모유지,보고서민감문구미포함. 유효모델/repeats/키/case입력전송전검증.
- [ ] **Step2 RED:** ai_service에서 `rtk proxy E:/AgentFit/tmp/worktrees/paired-review-evaluation/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_feature_relation_evaluation.py -v`. Expected:새runner없어FAIL.
- [ ] **Step3 implement:** 정확원문위치준비·스키마/해시검증·기존review_feature_relations호출·단일쌍trace판정·안전집계. 모델출력오류는행failed,checkpoint는호출외부에서전달한다.
- [ ] **Step4 GREEN/commit:** Step2 PASS,관련기능테스트도PASS. 커밋/task-done은새runner테스트명령.

### Task 2: 명시 CLI와 안전한 진행 기록

**Files:** Modify feature_relation_evaluation.py,tests/test_feature_relation_evaluation.py; create specs/.../feature-relation-regression/README.md.
**Interfaces:** main(argv=None)->int. --preflight/--live 상호배타required; --corpus(default고정파일),--corpus-sha256 required,--output(live필수),--env-file,--model(허용3개),--repeats1~3(default2).

- [ ] **Step1 RED:** preflight키조회/외부전송0,잘못된해시/기존output은key나runner호출전에거절,live배타생성/초기·각행저장,쓰기오류즉시중단,코드변경시gate실패·exit1. main주변의외부호출만fake하고파일/CLI실동작검증.
- [ ] **Step2 implement:** 기존keyloader/write_safe_json재사용. hash·설정·plan메타데이터와state를checkpoint로저장,코드hash동결검증. 정상run이라도회귀게이트미달exit1. 구성/경로오류parsererror2.
- [ ] **Step3 verify/commit:** 관련suite및전체unittest discover -s tests -v PASS(기존6skip허용). 사용법·범위기록. 커밋/task-done전체suite.

### Task 3: 48호출 회귀·리뷰·push

**Files:** specs/.../feature-relation-regression/validation.md,work/harness/feature-relation-regression/STATE.md. 실보고서는로컬tmp.
**Interfaces:** 커밋된코퍼스해시와고정제품코드로DeepSeek기본48행평가. 다른모델전환이나프롬프트수정은이실험중하지않는다.

- [ ] **Step1 preflight/live:** 전체12사례·정답과hash확인후전송없는CLI preflight PASS. 신규출력경로로48회명시live. 살아있는핸들을관찰하고관측타임아웃만으로재시작하지않는다.
- [ ] **Step2 interpret:** actual/expected/실패/uncertain·순서/반복을집계하고완료/중단행을정확보고. 합성문장근거로오류유형검토. 실제문서서비스정확도주장없음.
- [ ] **Step3 review/publish:** 독립전체리뷰1회→필요한수정1회RED→GREEN+전체회귀→기능push/정확CI. 문서만남으면task-done은base..HEAD diff --check.

## Self-review

코퍼스정답은모델요청에없고후보분류를평가대상으로혼동하지않는다. 원문해시·반복수·실행순서·안전출력형식이3작업에서일치한다. 정상실행과회귀통과를구분한다. 기존문서감사와전체실사용목표는계속남는다.
