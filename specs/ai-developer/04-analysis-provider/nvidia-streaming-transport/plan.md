# NVIDIA 스트리밍 전송 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 승인에 따라 직접 순차 수행한다. 제품 구현 계획은 아래 진단 근거로 추가한다.

**Goal:** 짧은비교로호환성을확인한NVIDIASSE전송을안전하게구현하고통합문서분석의긴요청을새평가한다.
**Architecture:** 첫2arm진단후순수SSE조립→시간제한child전송→기존통합함수default에연결한다. 모델/프롬프트/토큰상한/검증계약은유지한다.
**Tech Stack:** 기존 Python/urllib/subprocess/모델 어댑터, 새 의존성 없음.
**Spec:** specs/ai-developer/04-analysis-provider/nvidia-streaming-transport/spec.md

## Global Constraints

- feature/nvidia-streaming-transport, base efc94e0, 기존 source-name-expressions checkout 재사용.
- 제품 코드·공개 API·의미 기준 변경 전 읽기 전용 진단. 과거 실행14549는 종료됐으며 재시작하지 않는다.
- probe 최대2전송/각600초/응답16MiB,출력512토큰. 키·생성값·본문·헤더 로그 없음.
- 제품은기존8192출력토큰·각600초·64call유지. SSE wire16MiB,event/줄1MiB,완성응답1MiB,입력10MiB상한. 자동retry/fallback없음.
- subprocess stdoutS+완성envelope/E+허용code,stderr폐기,key는stdin만. 기존HTTP기본서비스는변경없음.

## Review Focus

- 응답 모드 외 차이: 정규화한 요청 해시 동일 여부 기록.
- 부분 스트림 종료를 성공 처리: `[DONE]`·stop·JSON·모델·원문 인용을 별도 게이트로 검사.
- 긴 자식 요청 잔존: 부모 subprocess timeout과 terminal 상태 확인.
- 실패를 분모에서 제외: 계획2 arm을 보고서에 미실행 포함 보존.
- 비밀 값 노출: stdout 고정 enum·숫자·bool, stderr폐기, 키는stdin만 사용.

### Task 1: 짧은 요청 비교

**Files:** 임시 E:/AgentFit/tmp/nvidia-transport-probe-20260930-v1.py 및 신규 JSON 보고서; Modify work/harness/nvidia-streaming-transport/STATE.md.
**Interfaces:** --preflight는 키조회/API0회. --live는부모가모드별child를순차호출; child는key/payload를stdin으로받고안전한숫자/enum/bool만반환.

- [ ] **Step1:** 기존 동작 추출 함수에 fake transport를 주입해 payload를 얻고 512토큰으로 고정한다. --preflight로 2arm,동일requesthash,0API 확인. Expected: 성공 또는 구체적인 로컬 준비 실패.
- [ ] **Step2:** --live 한 번 실행,실제핸들/종료 확인. 각600초이며 관찰timeout만으로 재시작하지 않는다. Expected:2arm의성공/실패/미실행을모두명시.
- [ ] **Step3:** code/driver/request hash·분모·키미노출을확인하고안전메타데이터만기록. 제품동작이없는일회성진단이므로TDD제품테스트를추가하지않는다.

### Task 2: 근거에 따른 구현 명세 구체화

**Files:** Modify 본 spec.md/plan.md; Create validation.md; Modify STATE.md.
**Interfaces:** Task1의실제HTTP/시간/종료/유효값메타데이터만사용한다.

- [ ] **Step1:** mode별결과와알수없는원인을구분한다. 짧은성공을긴문서해결로확대하지않는다.
- [ ] **Step2:** SSE가유효하면순수SSE검증·프로세스시간/메모리제한·기존NvidiaAnalyzer계약·통합함수옵션의구체계획을추가한다. 그렇지않으면실패유형에맞는대안과검증을명세에기록한다. 사용자자율승인내에서계속구현한다.

### Task 3: 완전한 SSE 응답 조립

**Files:** Create ai_service/agentfit_ai/nvidia_streaming.py,ai_service/tests/test_nvidia_streaming.py.
**Interfaces:** `_assemble_sse(chunks, expected_model)->bytes`는bytes청크iterator와NVIDIA3모델중하나를받아기존chatcompletion envelope반환. `MAX_STREAM_BYTES=16*1024*1024`, `MAX_EVENT_BYTES=MAX_RESPONSE_BYTES`, `_STREAM_CODES`는기존worker codes+PROVIDER_MODEL/INCOMPLETE_RESPONSE.

- [ ] **Step1 RED:** UTF8/CRLF/여러data줄/주석/임의byte분할에서JSONcontent만복원하고reasoning은제외. model/id불일치,choice복수/index오류,중복JSONkey,tool/refusal,finish뒤content/이중finish거절. `[DONE]`와finish누락은INCOMPLETE_RESPONSE,비stop은기존NvidiaAnalyzer로거절. wire/event/envelope초과거절,경계내작은응답성공. `python -m unittest discover -s tests -p test_nvidia_streaming.py -v` Expected:새모듈부재FAIL.
- [ ] **Step2 implement:** stateful줄/event조립은별도순수helper로이파일에유지. 기존solar._json/AnalysisError/MAX_RESPONSE_BYTES를재사용한다. 오류원문을노출하지않고usage누락은빈dict로보존한다.
- [ ] **Step3 GREEN/commit:** 새테스트및전체unittestPASS. task-done새파일테스트.

### Task 4: 기한이 있는 worker 및 통합 연결

**Files:** Modify nvidia_streaming.py,candidate_analysis_pipeline.py,tests/test_nvidia_streaming.py,tests/test_candidate_analysis_pipeline.py; Create agentfit_ai/nvidia_stream_worker.py; Update integrated-candidate-analysis/README.md.
**Interfaces:** `post_nvidia_streaming(payload,api_key,timeout)->bytes`; worker `_fetch(endpoint,payload,key,timeout)->bytes(S/E framing)`와stdin의endpoint/payload/key/timeout검증main. 통합함수는명시transport우선,없으면새전송사용.

- [ ] **Step1 RED:** 실제로컬HTTP서버+부모ENDPOINTpatch로자식이streamTrue/SSEAccept를보내고body복사본·key경로보존,정상chunk를기존NvidiaAnalyzer가파싱함. HTTP401/429/5xx/redirect·잘못된MIME/encoding·잘린stream·과대응답분류. slowheaders/slowevent는0.35초기한후PROVIDER_TIMEOUT,계속drip해도기한연장불가. stdout에부분body가남아도완성으로취급금지. 잘못된모델/timeout/키/과대입력은child0회. 통합default선택과명시fake우선을검증. Expected:새전송부재FAIL.
- [ ] **Step2 implement:** 기존providerworker와동일환경/입출력/기한패턴. workerread1(8192)로Task3조립기에전달,redirect금지/identity/MIME/크기검사. HTTP오류본문폐기·고정코드만. 통합NVIDIA기본전송변경,명시주입우선.
- [ ] **Step3 GREEN/commit:** 두테스트파일및전체suitePASS. README에SSE/정규화byte수/기한/남은실제품질관문기록. task-done전체suite.

### Task 5: 새 실제 H02·독립 리뷰·게시

**Files:** Modify validation.md,STATE.md; 임시driver/report는E:/AgentFit/tmp의새경로.
**Interfaces:** 기존H02driver를새파일로복제후NVIDIA전송을새어댑터로명시. pinnedsource/manifest/redacted는같고코드/driver해시·revision은이번구현으로고정한다. 개인본문/모델출력은메모리캡처,단계/개수/enum만출력.

- [ ] **Step1:** preflight키/API0회→freshlive1회,최대64requests/각600초. 실행핸들기록,같은핸들poll,종료전제품코드수정/재시작금지. Expected:성공/확인필요/실패와6부분검사의미평가여부를정확기록.
- [ ] **Step2:** 전체변경독립리뷰1회. Critical/Important만한번RED→GREEN수정·전체회귀,Minor기록/재리뷰없음. 의미검증과서비스준비를코드리뷰로대체하지않는다.
- [ ] **Step3:** feature push,정확구현CIsuccess확인,실측/제한/다음관문문서와원장완료. task-done문서최종범위diffcheck. 목표active유지.

## 자체검토

Task3응답은Task4의기존분석기가그대로검증한다. Task4부모기한은child의모든소켓활동과조립에적용되고default선택만바꾼다. Task5driver의명시전송도새어댑터로맞춰실험이일반모드를재사용하지않게한다. 짧은probe성공을서비스정확도로합산하지않는다. 사용자자율승인으로직접구현한다.
