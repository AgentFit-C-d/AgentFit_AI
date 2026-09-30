# NVIDIA 제한적 재시도 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 승인대로 직접 순차 구현한다.

**Goal:** 일시적 NVIDIA 5xx에서 완료된 앞 단계를 유지하고 동일 요청 한 번만 재시도하며, 모든 실패와 실제 호출을 계측한다.
**Architecture:** 통합 함수의 metered 전송에만 제한 루프를 둔다. Provider·Profile·의미 계약은 유지한다.
**Spec:** specs/ai-developer/04-analysis-provider/nvidia-transient-retry/spec.md
**Tech Stack:** 기존 Python/unittest/deepcopy/time, 새 의존성 없음.

## Global Constraints

- feature/nvidia-transient-retry, base8502da9, 기존 source-name-expressions worktree 재사용.
- 제품 I/O 전 옵션 검사. 최대64 실제 호출/시도당600초/8192토큰 유지. NVIDIA PROVIDER_UNAVAILABLE만 1회 재시도, 2초 대기, Solar 및 의미 실패 재시도 없음.
- 개인 문서·파생 문구·키 출력/추가 저장 없음. H02 API 평가 승인과 문서 발췌 열람 승인 대기는 구분한다.
- 독립 리뷰는 제품 구현 후 긴 실측 전에 한 번 수행한다. 이후 제품 코드를 고정해 실측 중 변경하지 않는다. 최종 실측·게시 감사는 부모가 맡는다.

## Review Focus

- 재시도가 계측 밖에 숨어 실제64호출 상한을 초과하는지, 예산이 없을 때 대기나 요청이 발생하는지.
- 첫 실패를 덮거나 모델·출력 오류를 재시도해서 성공률을 부풀리는지.
- transport의 입력 변이가 다음 시도의 모델·프롬프트·스키마에 남는지.
- timeout·취소·두 번째 오류 뒤 추가 호출이나 예외 본문 노출이 생기는지.
- driver의 최초 실패/재시도/전송 복구와 최종 의미 성공 분모가 구분되는지.

### Task 1: 시도별 계측과 제한적 복구

**Files:** Modify ai_service/agentfit_ai/candidate_analysis_pipeline.py,ai_service/tests/test_candidate_analysis_pipeline.py,specs/ai-developer/04-analysis-provider/integrated-candidate-analysis/README.md; Create ai_service/tests/test_candidate_transient_retry.py.
**Interfaces:** 함수의 `nvidia_retry_limit=1`, 허용0/1. 모든 trace행은 기존7키+attempt/retry_of_call_index/provider_error. 최대2전송,첫 PROVIDER_UNAVAILABLE만2초후동일깊은복사본재시도.

- [x] **Step1 RED:** 기존 ProviderFixture를 재사용해 NVIDIA 각단계 1회5xx→복구,마지막coverage만재전송/앞단계유지,반복5xx와두번째다른오류종료,다른오류·Solar·잘못된출력·미정결과재시도없음,0off/잘못된옵션I/O0,예산1/2/4경계/대기0,입력변이격리,기존collector인덱스독립,비밀없는실패행보존을테스트한다. 기존trace키검사에3개키추가. `python -m unittest discover -s tests -p test_candidate_transient_retry.py -v` Expected:새옵션/재시도/계측부재로FAIL.
- [x] **Step2 implement:** metered 안에서 모든 시도를 예산 검사 후 센다. 원 요청 snapshot을 NVIDIA에만 사용한다. AnalysisError의 허용코드만 기록하고 첫UNAVAILABLE외에는전파한다. 예산 소진 시 재시도 대기 전에 budget_exceeded를설정하고기존실패계약을유지한다.
- [x] **Step3 GREEN:** 새테스트,기존통합20건,전체suite를실행한다. README에기본1회·0off·추가시간·64call계측·전송복구와의미성공의차이를기록하고commit한다. task-done전체suite. Expected:모두PASS.

### Task 2: 독립 리뷰와 새 H02 평가

**Files:** 임시 새driver/report E:/AgentFit/tmp/nvidia-retry-h02-20260930-v1.py/.json; Create validation.md; Modify work/harness/nvidia-transient-retry/STATE.md.
**Interfaces:** 기존streaming H02driver를새경로로복제,nvidia_retry_limit=1명시. report에retry_attempts/transport_recoveries/failed_transport_attempts를trace에서계산한다. 이수치는최종품질점수와분리한다.

- [x] **Step1:** 새driver준비와API0사전검사. 제품코드전체에독립review1회,명세/원장판단포함. Critical/Important는한번RED→GREEN수정및전체suite,Minor는기록하고재리뷰하지않는다. Expected:블로킹결함해결후제품commit고정.
- [x] **Step2:** 최종revision/driver/code/source해시를고정한새보고서로H02freshlive1회실행. 같은핸들을terminal까지관찰하며재시작/제품수정금지. Expected:성공/확인/실패및6부분검사미평가분모보존.
- [x] **Step3:** 독립감사에서문서1·검사6·실제시도수≤64·연속call_index·attempt2가동일NVIDIA단계/모델의실패한최초행을참조·해시일치·재시도집계일치를검사한다. 실측5xx가없으면실제복구효과미관측으로보고한다. task-done은안전한감사스크립트. Expected:정확집계/해시PASS,모델품질실패는그대로남음.

### Task 3: 결과 기록과 게시

**Files:** Modify 본plan/validation.md,STATE.md,필요한최신README.
**Interfaces:** 실제검증/실측/리뷰범위만문서화하며실사용전체목표active유지.

- [x] **Step1:** 구현feature push와정확한구현revision CIsuccess확인. 검증된실측과미확인원인·한계를기록한다.
- [x] **Step2:** 최종문서commit/push,원장task-done문서범위diffcheck,작업트리상태확인. Expected:동기화/문서검사PASS,독립문서/서비스연동게이트는유지.

## 자체 검토

Task1 trace는Task2driver의실제시도계수와맞는다. 재시도2는최초call_index를참조하므로미리채워진collector에도예산이흔들리지않는다. 리뷰를실측전완료해보고서코드해시를고정한다. 모델별판단/대표기능/기본HTTP변경은없다.
