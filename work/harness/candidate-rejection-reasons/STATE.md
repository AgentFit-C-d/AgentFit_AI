# 상태

- 전체 목표: 실사용 가능한 AgentFit AI. active, 완료 아님. 설계·계획·구현 자율 진행과 feature별 push는 사용자 승인됨.
- 이번 기능: feature/candidate-rejection-reasons, 코드2063f0b. 기본 서비스/공개 Profile은 변경하지 않았다.
- 완료: 탈락 ID별 사유 일대일 검증, 선택형 사유 수집,8개 회귀 테스트, 독립 리뷰, push, Linux CI36636710843 success. 전체885건879pass6skip.
- 실측: H02 동일183개 후보·DeepSeek·explicit-v1로 기존/사유 검토 각7호출. 두 모드 모두 지정6/6이며 확인 필요. 기능17→14, 외부 연동5→1은 개수일 뿐 정확도가 아니다.
- 종료 확인: PID9744, 셸82604 exit0, candidate-rejection-reasons-h02-20260930-v1.json finished/코드불변. 현재 이 실험의 활성 프로세스 없음. 결과 파일을 덮어쓰거나 중복 실행하지 않는다.
- 근거: specs/ai-developer/04-analysis-provider/candidate-rejection-reasons/{spec,plan,validation}.md. 승인된 실제 원문은 Git/진단 파일에 저장하지 않는다.
- 남은 문제: 같은 기존 요청도 판정이 달라짐. 사유 모드도 기대효과를 유지하거나 명시된 기능을 제거함. 커버리지 단계가 미확정 기술 필드를 근거 없이 누락으로 지목함. 다른 문서·반복·실제 HTTP/Spring 확인 및 저장 미완료.
- 다음: 고정 후보와 명확한 의미 관찰 기준으로 다른 검토 모델을 비교한다. 필요하면 탈락/누락의 근거와 불일치 상태를 보존하는 구조로 보완한다. 사유 코드 유효성과 의미 정확성을 구분하고 기본 서비스 승격은 보류한다.
- 보호 대상: 다른 worktree의 사용자 소유 work/harness/service-readiness는 수정하지 않았다. 이 worktree는 후속 작업 재사용을 위해 유지한다.
