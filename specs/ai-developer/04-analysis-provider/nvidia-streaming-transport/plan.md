# NVIDIA 전송 진단 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 승인에 따라 직접 순차 수행한다. 제품 구현 계획은 아래 진단 근거로 추가한다.

**Goal:** 직전 302초 5xx를 짧은 동일 요청의 응답 모드 비교로 좁힌다.
**Architecture:** 창작 문서의 기존 동작 추출 payload를 고정하고 일반/stream 두 child를 순차 실행한다. 부모가 600초를 강제하고 안전 메타데이터만 원자적으로 저장한다.
**Tech Stack:** 기존 Python/urllib/subprocess/모델 어댑터, 새 의존성 없음.
**Spec:** specs/ai-developer/04-analysis-provider/nvidia-streaming-transport/spec.md

## Global Constraints

- feature/nvidia-streaming-transport, base efc94e0, 기존 source-name-expressions checkout 재사용.
- 제품 코드·공개 API·의미 기준 변경 전 읽기 전용 진단. 과거 실행14549는 종료됐으며 재시작하지 않는다.
- probe 최대2전송/각600초/응답16MiB,출력512토큰. 키·생성값·본문·헤더 로그 없음.

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

## 자체검토

현재 probe는 같은 기능의 짧은 입력에서 응답 방식만 바꾼다. 신규 서비스 성공률을 주장하지 않으며, 기존 실제 문서 실패 기록을 유지한다. 제품 변경은 후속 명세가 구체화된 뒤 RED부터 시작한다.
