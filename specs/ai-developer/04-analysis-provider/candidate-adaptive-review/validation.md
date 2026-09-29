# 제한적 분할 검토 검증

- 미구현 adaptive_review 인자와 CLI 옵션의 실패를 확인한 뒤 구현했다.
- 20개 부모 실패를 5개씩4개로 정확히 나누고 다음 정상 묶음과 누락 검사로 이어지는 경로를 검증했다. 하위 묶음 실패는 재분할하지 않으며 누락 검사로 진행하지 않는다.
- 잘못된 계약·timeout·다른 모델·5개 이하 묶음·기본 모드는 재시도하지 않는다. 원문 누락 검토의 length도 분할하지 않는다.
- 실패한 부모의 validated=false를 남기고 모든 자식이 검증돼야 recovered=true가 된다. 부모의 잘린 부분 응답은 사용하지 않는다.
- 통합 테스트의 backend 기대값을 기존 공개 계약인 배열로 수정했다. 서비스/Profile 형식은 변경하지 않았다.
- 관련19개, 전체836개 실행(6개 건너뜀, 나머지 통과). diff 공백 검사 통과. 실제 CLI에서 split-review 없는 adaptive-review는 호출 전에 거부됨을 확인했다.
- 독립 리뷰에서 수정이 필요한 P0–P2 결함 없음. 리뷰어의 합성7건(하위 ID 누락·중복, 오류 ID 범위·중복, timeout, 다른 모델, 진단 없는 복구·부모 부분 응답 폐기)도 통과했다. 해당 경계를 전부 영구 회귀 테스트로 추가하지는 않았다.
- 코드 커밋46c9b4d를 feature/candidate-adaptive-review에 push했고 Linux CI36622279410 성공을 확인했다. 실제 H02 평가는 아래와 같이 종료됐다. 모델 정확도 개선 및 실사용 가능 여부는 아직 미입증이다. 초기 누락·의미적 오판·원문 누락 호출 자체의 길이 제한은 이번 복구 범위 밖이다.

## 실제 H02 결과 — 2026-09-30

- 안전한 집계 결과: `E:/AgentFit/tmp/candidate-adaptive-review-h02-20260930-v1.json`. 시작 셸 세션51531은 종료됐다. 중복 실행하지 않는다.
- 최종 `needs_confirmation`, 실패0, 자동 완료0. 분석 시간614,801ms(약10분15초, 문서 전처리 제외).
- 후보137개, 원문에 없는 추출 인용3개 거절, 검토 이슈16개. 확인 필요 필드는 project_name/project_type/domain/frontend/ai/deployment/external_integrations다.
- 후보20개씩5묶음과 전체 누락 검토1회가 모두 계약 검증을 통과했다. 종료 사유는 전부 stop이며 후보 검토 출력은4,354~6,669토큰, 누락 검토는1,892토큰이었다.
- **length가 없어 하위 분할 복구는 발동하지 않았다.** 이전 실패 실행과 최초 추출·판단도 달라졌으므로 이번 완주나 시간 감소를 adaptive 변경의 인과 효과로 주장할 수 없다.
- 제안 결과의 지정6항목 중4개 일치. C01(project_name)은 grounded/classified/reviewed에서 일치하고 projected에서 불일치했다. C03(backend)은 최종 null 기대를 위반했다. C02/C04/C05/C06은 최종 일치했다. 이는 전체 정확도나 모든 후보의 의미 검증 결과가 아니다.
- 긍정 항목의 단계 진단은 원문 후보에 정답 문자열이 포함되는지 확인한다. 후보값 전체의 정확성이나 동의어 관계를 입증하지 않는다. 미정 항목은 최종 단계만 관측하므로 backend 오판의 최초 발생 단계는 아직 특정할 수 없다.

## 다음 행동

실사용 기본값으로 승격하지 않는다. 검토를 통과한 backend 오확정과 프로젝트명의 최종 변환 탈락을 원문·동일 후보 기반으로 분리 조사한다. 한 번의 완주를 반복 안정성으로 해석하지 않는다. 원문·응답·Profile 값은 공개 기록에 추가하지 않았다.

## 실행 추적 기록

기존 승인된 H02를 source-occurrences/stage-diagnostics/split-review/review-diagnostics/adaptive-review로 실행했다. PID26276, 시작 UTC2026-09-29T19:52:18.2253049Z, 시작 셸 세션51531. PID와 시작 시간을 함께 확인해야 한다. 이전 진단 평가 PID30404와 셸34082는 종료됐다.

- 결과: E:/AgentFit/tmp/candidate-adaptive-review-h02-20260930-v1.json
- 프로세스 기록: E:/AgentFit/tmp/candidate-adaptive-review-h02-20260930-v1-process.json
- 실행 로그: 같은 이름의 .stdout.log/.stderr.log. Git에 추가하지 않는다.
- 최종 JSON과 셸 종료를 확인했다. 이 실행은 완료됐고 후속 실험은 별도 결과 경로로 진행한다.
