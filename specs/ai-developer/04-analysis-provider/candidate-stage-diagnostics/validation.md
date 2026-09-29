# 단계별 정답 도달 진단 검증

- 선택형 관측은 분석 상태의 깊은 복사본을 사용한다. 관측 함수가 상태를 지우거나 정답 표식을 추가해도 Profile과 모델 요청이 바뀌지 않는 회귀 테스트를 통과했다.
- 양성 정답의 최초 미일치를 grounded/classified/reviewed/projected로 구분한다. 실행되지 않은 단계는 null·unobserved다. expect_null은 최종 Profile에서만 채점한다.
- 모델 호출 실패 전에 도달한 단계가 결과에 보존된다. 확인 필요 제안의 실패 ID는 `suggestion_failed_check_ids`로 자동 완료 점수와 별도로 기록한다. 원문·정답 문자열·후보 값은 진단 결과에 포함하지 않는다.
- 전체 로컬 테스트: 822개 실행, 6개 건너뜀, 나머지 통과. diff 공백 검사 통과.
- 코드 커밋 `8977ed8` push와 Linux CI 실행 36613246144 성공을 확인했다.
- 승인된 H02의 source-occurrences·stage-diagnostics 실행은 약 274초 후 `COVERAGE_REVIEW_FAILED / INCOMPLETE_RESPONSE`로 끝났다. 자동 완료·제안 결과는 없어서 최종 채점하지 않았다.
- C01(project_name), C05(external_integrations), C06(features)의 양성 정답 문구는 모두 grounded=true, classified=true였다. 검토 응답이 미완료라 reviewed/projected는 null이다. C02(database), C03(backend), C04(frontend)는 expect_null 확인 항목이어서 중간 단계에서는 채점하지 않았다. 이 결과를 3/6이나 6/6 정확도로 표현하면 안 된다.
- 이번 실행에서는 양성 정답 누락이 위치 고정·판정 전에 발생하지 않았고, 전체 검토 응답의 미완료가 직접적인 중단 원인임을 확인했다. 이전 성공 실행의 미일치 두 항목과 같은 원인인지는 아직 확인하지 못했다.
- 진단의 양성 정답 검사는 기존 contains_any 규칙이다. 값의 포함 여부가 맞아도 문서 전체의 누락·잘못된 추가 항목·오확정·근거 의미가 모두 맞음을 뜻하지 않는다.

## 다음 행동

기존 fieldwise-semantic-review 기록에서는 비기능 필드 검토가 끝나도 기능 구역 검토가 미완료되는 문제가 있었다. 새 후보 우선 경로는 후보 라벨 검증과 원문 전체 누락 검증을 한 호출에 합치고 있다. 다음 실험은 확정 후보를 작은 묶음으로 검증하고, 잘못된 후보를 제거한 뒤 전체 원문과 필드별 고유 값으로 누락만 별도 검토하는 방식으로 작업을 나눈다. 전체 단계의 유효 응답이 있어야 완료하도록 하며 기존 단계 진단으로 정답 소실도 함께 추적한다. 단순 출력 한도 증가나 보류 조건 완화는 하지 않는다.
