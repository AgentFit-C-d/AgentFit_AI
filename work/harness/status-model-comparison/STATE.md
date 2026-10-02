# 정의 통일 버전의 다른 모델 비교 — 계획 상태

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
