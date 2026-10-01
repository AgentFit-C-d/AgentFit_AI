# 실행 기록 — classification-instruction-evaluation/plan.md

2026-10-01 14:02 UTC 시작 / 로컬 구현·검증 상한15:02 UTC.
기준 commit `b35b2c9`, 브랜치 `feature/classification-instruction-comparison`.

## 사용자 승인

현재 요청에서 기존 지침과 명확한30개 정답을 고정하고 무료 NVIDIA 최대8회·재시도0의 한 쌍 실행을 승인했다.
FR16·LS15는 주 점수에서 제외하되 판정·근거는 별도 보고한다. 서비스 적용 및 큰 goal 재개 금지.
기존 plan/spec의 계획 작성 단계 호출0 제한은 이 후속 승인으로 실행 단계에서만 대체됐다.
정답·지침 파일 자체는 수정하지 않고 승인 사실을 이 실행 기록과 freeze에 분리한다.

## 고정 조건과 사전 판단

- 기존 U payload/gate/source registry는 수정하지 않는다. U+C에 승인된 지침을 LF 하나 뒤에 그대로 추가한다.
- Task1→Task2: 후보·정답·원문·지침은 기존 계획 commit의 파일 그대로 사용. 새 응답으로 정답을 바꾸지 않는다.
- Task2→Task3: 로컬 테스트와 독립 코드 검토 후 코드·자료를 freeze하고 최초 실패에 전체 실행을 중단한다.
- Ruling: 기존 CallGate는18회와 A→B 두 구간에 고정돼 있다. 수정하지 않고 이번8개 요청의 정확한 순서와600초/전체90분을 제한하는 작은 별도 transport gate를 둔다. 의미 분류·근거 검증은 바꾸지 않는다.
- Ruling: 실행 기록은 기존 harness 경로에 둔다. `.superpowers/`의 다른 작업 기록은 수정·삭제하지 않는다. 사용자 보존 지침을 우선한다.
- 무료 근거: `nvidia-free-access-20261001-user-confirmation.json`의 사용자 확인, 17:32:45 UTC 만료.
  현재14:02 UTC 유효. 계정 청구 화면이나 잔여 quota를 직접 조회했다는 뜻은 아니다. 매 호출 전 검증하고 거절/실패 시 중단한다.
- 큰 goal은 get_goal에서 paused 확인.

## 진행

- Task1: 정답·지침 승인 확인 완료. 자료와 코드의 최종 freeze는 로컬 검증 뒤 실행.
- Task2: 신규12개 테스트가 미구현으로 실패하는 RED를 확인한 뒤 구현,12개 GREEN 확인.
  전체 suite1353개 실행/1346통과/7 skip/실패0,71.417초.
  로그 `E:/AgentFit/output/classification-instruction-tests.log`.
  고정 응답 테스트이며 모델의 실제 의미 판단 개선을 증명하지 않는다.
  요청 동등성·8회 상한·실패 중단·정상/오확정/보류/인용/누락 분리 검증 완료. 독립 코드 검토 중.
- Task3: 미실행, 실제 모델 호출0.

## 사전 자료 보존 검증

- 기존 기준선 freeze140개 해시 일치.
- 승인 commit b35b2c9 대비 평가 specs 디렉터리 diff 없음: 지침·정답·원문 모두 그대로.
- 기존 validate_free_access를 reserved_calls=8로 오프라인 실행하여 현재 유효성 확인.
- ai_service/README.md와 ai_service/pyproject.toml은 존재하지 않아 root README 및 CI에서 실제 unittest 명령을 확인했다.

## 독립 코드 검토와 수정

- 검토자는 nullable token 합산으로 정상8회 이후 보고서가 사라지는 Important1건과 실패 응답 사용량 누락을 발견했다.
- 실제 Solar parser의 count가 None을 반환하는 경로를 확인하고 로컬13개 테스트 중2개 실패로 두 증상을 재현했다.
- Ruling: 실패 응답 사용량 누락도 동일 집계의 보고 정확성 문제로 Important로 분류하여 한 번의 수정에 포함했다.
  호출별 사용량을 정규화 성공 여부와 분리해 남기고, 전체 사용량은 미확인 호출이 있으면 null, 알려진 합과 미확인 횟수를 별도 보존한다.
- 새 모델 호출 없이 사용량 미제공 정상8회와 malformed 응답의 사용량 보존을 고정 응답으로 검증한다.
- 검토자가 판단하지 않은 실제 의미 성능은 이번8회에서 측정하고, 청구 화면/잔여quota 독립 확인은 미검증으로 보고한다.

## 실행 직전 검증 완료

- 두 집계 증상 RED→GREEN, 신규13개 통과.
- 최종 전체1354개 실행/1347통과/7 skip/실패0,70.391초.
  `E:/AgentFit/output/classification-instruction-tests-final.log`.
- 코드 검토의 Important를 한 번의 수정으로 해결했다. 남은 Critical/Important 및 deferred minor 없음.
- 호출0 상태에서 커밋 후 입력·지침·정답·코드를 freeze하고 실제8회 실행 단계로 진행한다.

## 보존

기존 dirty 상태인 semantic-confirmation-guard/STATE.md, STOP-20261001.md, .superpowers/, Docs/analysis/를 건드리지 않는다.
새 결과는 `E:/AgentFit/output/classification-instruction-v1/`에만 작성한다.
