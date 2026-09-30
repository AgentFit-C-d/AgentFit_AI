# 검토 계약 오류 진단 상태

## 목표·권한

- 전체 실사용 목표 active. 설계·계획·구현 자율 승인, SDD·직접 구현·기능별 feature push 유지.
- 이전 목표 턴은 상태 보고로 no progress. 현재 e544650의 clean checkout과 미구현 진단 경로를 확인했고 이번 기능 구현으로 진행한다.
- checkout E:/AgentFit/tmp/worktrees/integrated-input-guard 재사용. branch feature/review-contract-diagnostics, base e5446502562a8ac5452f740e73fb6675e63ecdfc.

## 현재

- Task1 명세·계획 작성. 수락 조건을 완화하지 않고 실패 원인 관측만 추가.
- 실제 GLM5번째 검토의 정확한 원인은 아직 미확인. 과거 원문 응답은 보관하지 않아 복원하지 않는다.
- 새 테스트 RED→최소 구현→GREEN/전체→독립 리뷰→새 H02 평가 순서.

## 경계

- 원문/파생 발췌 표시 승인 및 Spring 위치 질문은 답변 대기. 새 평가에서는 기존 승인된 개인정보 제거 API 전송만 수행하고 내용은 출력하지 않는다.
- 실사용 완료는 모델 품질·확인/저장·Spring 연동·실패 원본 7일 만료 등 근거가 더 필요하다.
