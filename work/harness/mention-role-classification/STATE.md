# 진행 상태

- 작업: 역할/출력 필드 혼동 하나. 큰 실사용 goal은 paused.
- base: 2a3a6badb26cb2835877217e0002c6d19474d3c3, branch feature/mention-role-classification.
- 기존 중단 문서·.superpowers·test_nvidia_service.py의 내용 차이 없는 M 보존. 별도 커밋 대상에서 제외.
- 원인: id/field/status와 근거 위치만으로 후보 자체가 제공자 이름인지 행동/역할인지 일관성을 검사하지 못함.
- 명세/계획/분류 기준 작성 → 고정 평가 세트 → 역할 검증 RED → 구현 → 로컬/실제 비교 완료.
- 예산: NVIDIA 무료 확인 범위만24호출 이하, 재시도0, 호출당180초, 전체30분, 추가 튜닝 없음. 유료 실험은 보류.

## 결과

- 고정 응답: 같은18후보/정상11개, 오확정7→0, 정상누락0→0, 확인필요0→7.
- 실제: 무료 DeepSeek18호출 완료, 재시도0. 일반기존/일반prompt/역할구조화의 오확정2/1/0, 정상누락0/0/0, 확인필요0/0/2, 불명확후보 확인의무유실1/1/0.
- 실제 기존 오확정은 domain 오분류다. 원래 Payments→external 오류는 이번 작은 후보 세트에서 재현되지 않음. 구조화 이전/이후의 인과 비교가 아니라 경로 비교. 고정 정답/채점 완화 없음.
- 일반 prompt는 미채택·철회. 선택형 semantic_assessment=True 분류기의 역할 검증만 반영. 기본 경로 미해결 사실을 결과 보고에 명시.
- 구조화 코드/의존 해시 동일, 일반prompt 당시 파일별도보존. output/mention-role-classification-v1 summary.json 참조.

## 검증과 리뷰

- 전체 unit1278 실행/7skip/1271pass(통합 테스트1건 추가 전), 최종 역할8pass, 기존semantic19pass, 전체contract47pass.
- 독립 리뷰 Important: 일반 경로 ambiguity 유실. 일반prompt채택철회 및 미해결기록. 새 통합 테스트는 분류/pipeline/초안 결과를 수동 수정하지 않고 후보·질문 보존 검증.
- 새 mentionKind HTTP/mock 저장 유지 확인. 모델confirmed와 사용자확정 분리 유지. 실제 Spring미검증.
- 최종 보고: specs/ai-developer/mention-role-classification/results.md.

## 변경 파일·마무리

- runtime: candidate_mention_roles.py 신규, candidate_semantic_assessment.py 수정. 일반 candidate_first_profile.py는 최종 내용차이 없음.
- tests: test_mention_role_classification.py, mention_role_cases.json, 기존 semantic guard/helper·HTTP 계약 tests.
- specs: mention-role-classification/{spec,plan,results}.md.
- harness: 이 STATE, prepare.py/evaluate.py/summarize.py.
- 코드/명세/결과 커밋 `e431f1fddff0b1f1a7fd06362a843789b4c5a1fe`를 origin/feature/mention-role-classification에 push 확인.
- 해당 코드 커밋 Linux CI `36824869523`: core-flow-runtime, integrated-runtime, unit-and-worker-memory, contract-mock **4/4 success**. 이 기록의 후속 문서 커밋은 운영 코드나 테스트를 변경하지 않음.
- 최종 diff 확인 완료. 기존 semantic-confirmation-guard 중단 기록, 미커밋 Docs 분석, test_nvidia_service.py와 일반 분류 파일의 내용차이 없는 M, .superpowers 보존.
- 이번 한정 수정·검증 종료. 큰 goal paused 유지. 다음 구현/모델 호출 없음. 기본 경로 유실·새 문서 전체 일반화·실제 Spring은 완료로 처리하지 않음.
