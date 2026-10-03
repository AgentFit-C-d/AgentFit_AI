# Mention role cause analysis

- 2026-10-03 승인: 원인 분석·최소 수정안·실패 재현 테스트·후속 비교 계획만. 제품/지침/스키마/골드 변경0, 복구 확장0, 모델/외부 전송0, 큰Goal paused.
- 브랜치 feature/mention-role-cause-analysis, 기준b0347ba. 기존 다른 dirty 파일 보존.
- 확인: 두 실행 title AgentFit=project_name/external_service/confirmed→needs_confirmation. v2 제목/소개는 추가 인용 occurrence 오류도 있어 grounding이 첫 거부 경계, v3는 유효 근거 후 역할 불일치. Codex=external_integrations/external_service/confirmed→supported. v2 GLM도 놓침, v3 검토 미완료.
- 정상 대조 GitHub에도 quote occurrence 오류가 혼재하므로 역할 개선 효과로 합산하지 않는다. 16개 대표 발생 위치에서 인용 결함은 이름2·GitHub3.
- 완료: 39개 실제 분류 요청의 messages/schema가 현재 builder와 동일함을 확인. 저장16행 서버 재현 일치. 10필드×6역할 합성 검사에서 현재10정상조합 supported/50불일치보류.
- 별도 발견: tentative/proposed+나머지명확축은 excluded. 역할 원인과 분리한 미수정 서버 정책 문제.
- 산출물: ai_service/tests/test_mention_role_cause.py; work/harness/mention-role-cause-analysis/reproduce.py; specs/ai-developer/mention-role-cause-analysis/{plan.md,report-20261003.md,comparison-plan.md}.
- 증거: E:/AgentFit/output/mention-role-cause-analysis-20261003-v1. 원본 두 실행 폴더·source·gold 전후 해시 일치. 새 모델0, 외부전송0.
- 테스트18함수: 13통과+5예상실패(과거모델4, 별도합성정책1). 예상실패는 AssertionError임도 확인. 모델 정확도 개선·최종40의미 재평가 아님.
- 제안: MENTION_ROLE_INSTRUCTION 하나에서 기존other/metadata와 지원Client/실제provider 관계 명확화. schema/server/모델/골드 변경 불필요. 독립payload의 기존8후보 A/B 최소2호출 계획만 작성. 별도 승인 전 실행 금지.
- 큰 Goal paused를 get_goal로 재확인. 기존 unrelated dirty 보존.
- 독립 읽기 전용 리뷰 완료: 18개 좁은 검증을 따로 실행해 13통과+5의도한 assertion 실패 확인. 중요 발견 없음, 보고서 코드 링크 줄 번호만 수정.
- 종료 상태: 요청한 원인 분석·실패 재현·최소 지침안·2호출 후속 계획 완료. 외부 전송 없이 로컬 feature 브랜치에만 커밋. 실제 지침 수정·모델 비교·복구 재개는 승인 전까지 수행하지 않는다.
