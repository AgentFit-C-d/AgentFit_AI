# 문서 입력 통합 검증 상태

- 목표: PDF/Markdown → 실제 AI 파서·자식 프로세스 → 사용자 확인·수정 → mock 저장.
- 브랜치: feature/document-input-runtime, 시작 ae61e7fa081d7502153c58d5fd2fec7b418543ff.
- 별도 작업트리: E:/AgentFit/tmp/worktrees/document-input-runtime.
- 설계/계획: specs/ai-developer/document-input-runtime/{spec,plan}.md.
- 권한: 기존 목표의 자율 설계·직접 구현·feature push 승인. 실제 Spring 미제공: mock/계약까지.
- 예산: 추가 외부 호출 0/유료 0/재시도 0/배포 0. 대상 120초, suite당 180초, CI 관찰 10분.
- 판단: native create_worktree가 root 저장소 소유권 오류로 실패했다. 전역 trust 변경 없이 해당 저장소에만 safe.directory를 지정하여 Git worktree 생성. 기존 평가 작업트리를 변경하지 않았다.
- 진행: 새 통합 시험3건(잘못된 입력8종 포함) 통과. 단일 최종 리뷰 Important1(누출 검사의 JSON 이스케이프 누락)을 주입 실험 RED→GREEN 수정. 수정 후 전체 unit1146pass5skip/runtime23/contract36/core8, 총1213pass5skip, 모두 exit0. 제품 코드 변경0. 최종 commit/push/CI 단계.
- 다음 독립 작업: 실제 평가가 제공자5xx의 실패 모델·단계 정보를 보존하지 못하므로, 원문/키를 제외한 기존 call_trace의 평가 전달을 SDD로 설계한다. 추가 외부 재시도는 하지 않는다.
- 실제 평가: session91387는 exit1로 종료. PUBLIC-01/run0 PROVIDER_UNAVAILABLE(HTTP5xx범주),1249.898986초. 전체1/30 종료,29미실행,pending0. 재시작/재시도/유료대체 금지. 결과는 다른 작업트리의 specs/ai-developer/nvidia-evaluation-variant/live-result.md와 output/independent-profile-v1/runs-nvidia-only-dfd33a2에 보존.
- 미검증: 실제 모델 품질/사람 gold/실제 Spring·DB/운영 배포/복잡한 PDF·OCR.
