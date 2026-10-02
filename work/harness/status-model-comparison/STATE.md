# 정의 통일 버전의 다른 모델 비교 — 계획 상태

## 2026-10-02 실행 승인 / 재개

- 사용자 최신 메시지가 두 엔드포인트의 무료 확인과 최대8회 실행,첫 GLM 본 배치 호환성 검사를 승인했다.
- 브랜치 feature/status-model-comparison. 실행 기준 f2f9ea2. 시작06:44 UTC, 작업/호출 종료 상한08:10 UTC.
- Task1 진행: 새로운 독립 실행기와 고정 응답 테스트. Task2 실제 한 쌍. Task3 결과 보고 후 종료.
- Ruling: 과거 무료 기록을 재사용하지 않고 이번 사용자 확인에 한정한8회/이번 실행 종료시 만료 기록을 만든다.
  계정 잔량·청구 화면의 독립 조회는 미검증으로 보고한다.
- Ruling: NvidiaAnalyzer는 GLM의 temperature/reasoning/chat_template_kwargs를 자동 변경하므로 사용하지 않는다.
  같은 Solar 응답 parser를 사용하되 실제 payload를 변경 없이 전달하는 독립 sender를 둔다.
  전송 전후 동일성 테스트로 model 외 차이를 차단한다.
- Ruling: 상태 기록은 기존 work/harness/STATE 관례를 유지한다. 기존 .superpowers/와 동결된 계획은 수정하지 않는다.
- 사전 인터페이스 검토: Task1 package.jobs→Task2 gate/sender는 모델별 ID검사가 필요.
  Task2 records/evidence→Task3는 기존 score/diagnostics를 그대로 재사용한다.
- RED: 신규11개 테스트 모두 model-only harness missing으로 실패 확인.
- GREEN: 신규11개 통과,전체1373실행/1366통과/7skip/실패0,69.636초.
  로그 E:/AgentFit/output/status-model-comparison-tests.log. 실제호출0.
- load_saved: 기존209개 입력/코드 hash 검증. 두 모델8개 job 생성,model 외 payload 변경0.
- 독립 검토 status_model_comparison_review 진행 중. 검토 전 실제 실행하지 않는다.
- 독립 검토 완료: Critical0/Important2/Minor0. 근거 배열 maxItems 초과 후 계속 호출,
  해시/기록 I/O 동안 지난 만료 시각을 반영하지 않는 결함을 고정 응답·가짜시계3테스트로 RED 재현.
- 수정: 기존 schema의 maxItems만 wrapper에서 사전검사,전송 직전 무료/전체 잔여시간 재계산.
  기존 normalizer/score/공개schema 변경0.14테스트 GREEN. 전체 회귀 재실행 중.
- Final Ruling: reviewer가 실서비스 옵션 준수·계정 잔량·모델 성능을 판단 유보한 것은
  코드 검토로 확인할 수 없는 항목이다. 새 사용자 무료 확인을 근거로 승인된 본 배치만 실행하고,
  실제 옵션 적용 여부와 계정 화면 독립 확인은 미검증으로 보고한다. 추측으로 성공 주장하지 않는다.
- 보류 minor없음.실제호출0.새 요청 조건을 바꾸지 않는 실행기 결함 수정만 했다.
- Task1 완료: 최종 전체1376실행/1369통과/7skip/실패0,69.163초.
  E:/AgentFit/output/status-model-comparison-tests-final.log. 신규14개 GREEN.
  두 Important 수정은 RED→GREEN 및전체suite로 검증,추가 리뷰 반복없음.
- get_goal로 큰goal paused 확인. 다음은 freeze 후 live1회,실패시 재실행금지.
- Task2 시작: 실행 commit59fc184,freeze220파일,출력 E:/AgentFit/output/status-model-comparison-v1/.
  실제 live 세션10585.첫 GLM FR/1 요청 전송 중.중단 시 live를 다시 실행하지 않는다.
- Task2 종료: 세션10585 exit1.5번째 DeepSeek LS/1에서 기존 SSE transport INVALID_RESPONSE.
  실제5시도(D3/G2),완료4,실패1,미실행3,재시도0.412.52초.재시작·옵션변경·대체호출0.
- 완료FR: D→G 모델/서버오확정2→0,정상누락0→0(10개보존),올바른제외3→1,
  주보류0→4,전체보류1→5,인용결함0→0.시간66.01→324.12초.
- FR16 양쪽 external_integrations/tentative/needs_confirmation,42행 모금근거선택.
  LS15 배치미실행으로230행 암호화해제 counter 선택여부 미평가.미선택으로 집계하지 않는다.
- 실패5번째는 조립응답이 반환되지 않아 response.json없음.정확한 HTTP/SSE 원인 미확인;
  모델의 의미 오류·옵션 거절로 단정하지 않는다.추가 재현 호출 없이 종료한다.
- Task3 완료: results.md/results.json 추가.사후221개 hash일치,model외요청차이0,
  완료문서지표독립재집계일치.원문/후보32/정답과완료4응답보존.불완전LS는점수비교에서제외.
- 최종제약: 무료근거는이번사용자확인,잔량독립조회없음.옵션의서버내부적용미확인.
  지침·정답사후변경0,서비스적용0,큰goal paused.브랜치 push후보고종료.

2026-10-02 KST. 브랜치 feature/status-model-comparison-plan, 기준224a0d7.
기존 document-input-runtime worktree 사용. 사용자 요청은 계획까지만이며 실제 호출 권한이 아니다.

## 완료

- 실제 저장 US 요청4개와 score/normalizer/transport 경로 확인.
- 이전 freeze199개 파일 해시 일치. 기존 결과·지침·후보·정답 변경0.
- 공식 NVIDIA 자료에서 GLM5.3 모델ID/무료 endpoint/문맥1M 확인.
- strict response_format와 thinking=false의 해당 hosted 지원, 계정의 현재 무료 범위는 미확인으로 명시.
- spec.md, model-check.md, plan.md, input-freeze.json, frozen-system.txt에 범위·고정 입력·한도 기록.
- 계획 자체 점검: 지침/model 외 차이 금지,32개/30점수/모호2개 분리,새 무료 근거,
  8회·retry0·600초/5400초,중단 후 재진입 금지,LS07/FR16/LS15 검증 포함.

## 결정과 남은 조건

GLM5.3은 조건부 후보다. 일반 OpenAI 호환 또는 NIM 컨테이너 문서를 정확한 hosted schema 지원으로
확대 해석하지 않는다. 무료 공개 표기는 새 계정 확인을 대신하지 않는다.
기존 무료 기록은 만료되어 사용 금지이며 과거 hash 검사는 실행 권한을 갱신하지 않는다.
새 호출·실행기 구현·서비스 적용0,큰 goal 중단 유지.
실행 승인과 새 무료 확인을 받은 후에만 계획의 Task1부터 진행한다.

## 최종 로컬 확인

- 새 manifest23개 hash 재검증 일치,기존199개 hash 재검증 일치.
- frozen-system.txt가 저장03-request의 system UTF-8 바이트와 일치(9,375자).
- 후보32/주점수30,FR84줄단위/LS305줄단위 확인. 실행 승인 플래그false.
- 제품·실행기 변경이 없는 문서 작업이므로 단위/통합 테스트는 실행하지 않았다.
- 신규6개 spec 산출물과 이 STATE만 커밋 대상으로 선택한다. 기존 dirty4항목 보존.

## 보존할 기존 미커밋 파일

work/harness/semantic-confirmation-guard/STATE.md, STOP-20261001.md, .superpowers/, Docs/analysis/.
이 요청에서 수정하거나 stage하지 않는다.
