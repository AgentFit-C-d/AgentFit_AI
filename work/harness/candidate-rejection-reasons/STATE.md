# 상태

- 전체 목표: 실사용 가능한 AgentFit AI. active, 완료 아님. 설계·계획·구현 자율 진행과 feature별 push는 사용자 승인됨.
- 이번 기능: feature/candidate-rejection-reasons, 코드2063f0b. 기본 서비스/공개 Profile은 변경하지 않았다.
- 완료: 탈락 ID별 사유 일대일 검증, 선택형 사유 수집,8개 회귀 테스트, 독립 리뷰, push, Linux CI36636710843 success. 전체885건879pass6skip.
- 실측: H02 동일183개 후보·DeepSeek·explicit-v1로 기존/사유 검토 각7호출. 두 모드 모두 지정6/6이며 확인 필요. 기능17→14, 외부 연동5→1은 개수일 뿐 정확도가 아니다.
- 종료 확인: PID9744, 셸82604 exit0, candidate-rejection-reasons-h02-20260930-v1.json finished/코드불변. 이 이전 실험은 종료됐으며 결과 파일을 덮어쓰거나 중복 실행하지 않는다.
- 후속 비교 종료: PID30648, 셸79888 exit1, 로컬 run-rejection-reason-models-h02.py, 결과 candidate-rejection-models-h02-20260930-v1.json finished/code_unchanged=true. GLM7호출 완료, Kimi는 첫 호출에서302,213ms 뒤 PROVIDER_UNAVAILABLE로 종료했다. Kimi 의미 점수는 없음. reasoned_review=True/183개 후보 고정. 이 종료된 실행은 재시작하지 않는다.
- GLM 완료 행: 사전16개15/16(C156 명시 동작 오제외), 지정6개4/6(C03 backend, C06 features 실패), 확인 필요. C016/C150 내부 서버 모듈이 backend로 남음. 고유 기능37개는 현30개 상한에 걸려 features=null. 7응답 전부 stop/계약유효,1,133,914ms. 한정16개 점수로 채택하지 않는다.
- 근거: specs/ai-developer/04-analysis-provider/candidate-rejection-reasons/{spec,plan,validation}.md. 승인된 실제 원문은 Git/진단 파일에 저장하지 않는다.
- 남은 문제: 같은 기존 요청도 판정이 달라짐. 사유 모드도 기대효과를 유지하거나 명시된 기능을 제거함. 커버리지 단계가 미확정 기술 필드를 근거 없이 누락으로 지목함. 다른 문서·반복·실제 HTTP/Spring 확인 및 저장 미완료.
- 다음: GLM 기존1·5번 묶음의 추론 강도만 low→max로 바꾸는2호출 실험을 준비했다. 실행 전 원문/후보/코드 및6개 판정 기준 preflight exit0. 드라이버 run-rejection-reason-effort-h02.py, 새 결과 candidate-rejection-effort-h02-20260930-v1.json. 기존 low는3/6이며 전체 문서 정확도가 아니다. 현재 기록 시점 아직 실호출 전이다.
- 구조 보완 후보: 원문 근거 없는 missingFields 계약과 대표 기능30개 이하 구성. 기존 section_feature_extraction.py의 section_curation_payload/normalize_section_curation은 source-selector용이며 ID 부분집합만 고른다. 후보 ID 방식에는 직접 연결돼 있지 않고 선택에서 빠진 후보의 의미 커버리지도 별도 검증이 필요하다. 사용자 요구를 충족하는 대표 기능 구성을 SDD로 이어간다. 사유 코드 유효성과 의미 정확성을 구분하고 기본 서비스 승격은 보류한다.
- 실행 전 기준은 model-comparison.md에 고정하고 f97fda3으로 push했다. 같은 기준의 기존 DeepSeek 일반8/16, 사유13/16은 과거 출력에 대한 개발자 관찰 집계이며 전체 문서 정확도가 아니다.
- 보호 대상: 다른 worktree의 사용자 소유 work/harness/service-readiness는 수정하지 않았다. 이 worktree는 후속 작업 재사용을 위해 유지한다.
