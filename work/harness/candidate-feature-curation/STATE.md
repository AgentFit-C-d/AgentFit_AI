# 상태

- 전체 목표: 실사용 가능한 AgentFit AI, active/미완료. 사용자가 설계·계획·구현 자율 진행과 기능별 push를 승인했다.
- 기능: feature/candidate-feature-curation, base a774923, E:/AgentFit/tmp/worktrees/source-name-expressions 재사용.
- 확인된 문제: H02/GLM 검토 후41개 기능 발생 위치·37개 표현이30개 한도에 걸려 features=null. 대표 기능30개 이하 사용자 요구 미충족.
- 결정: 원문 대표 ID와 전체 후보 분할을 제안하고 독립 포함 관계 검토 후 선택형 finalize에 반영. 미대표/미포함은 확인 필요이며 기존 잘못된 후보 분류나 원문 누락을 해결했다고 간주하지 않음.
- 현재: spec.md/plan.md 작성, 자체 일관성 검토. 아직 제품 코드/테스트 변경 없음. 직접 구현 예정이며 재승인 불필요.
- 선행 실험 진행: GLM max 스트리밍 임시 진단 PID2192, 셸14136, 드라이버 E:/AgentFit/tmp/run-rejection-reason-stream-h02.py, 결과 candidate-rejection-stream-h02-20260930-v1.json. 두 묶음 최대2호출. 첫 이벤트102,706ms에 수신했고 최종 응답은 아직 미확인. 기존 셸76468/79888은 종료됐으므로 재시작 금지. 스트리밍 실험의 코드 불변 확인을 마친 뒤 제품 코드 편집을 시작한다.
- 다음: 셸14136을 기다려 실제 HTTP/완료/의미 결과를 확인하고 진단 기록을 갱신한다. 이어 plan의 Task1 RED부터 직접 구현·검증·독립 리뷰·push/CI·실문서 대조를 진행한다.
- 전체 남은 관문: 대표 구성 외의 의미 오류/원문 누락, 여러 문서 반복, HTTP/Spring 확인 및 저장 연동. 기능 완료와 서비스 목표 완료를 구분한다.
- 보호: 다른 worktree의 사용자 소유 work/harness/service-readiness는 수정하지 않는다.
