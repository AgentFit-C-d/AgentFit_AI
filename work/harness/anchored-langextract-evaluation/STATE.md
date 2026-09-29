# 상태

- 상위 목표: AgentFit AI 분석을 실사용 가능한 수준으로 검증·개선한다. NVIDIA preview 모델 사용과 목표 범위의 계획·구현은 사용자 승인됨.
- 현재 기능: 반복 문구의 근거 위치를 LangExtract `candidate_attributes.anchor`로 선택형 평가한다. 기본 서비스·공개 Profile은 유지한다.
- 기준: `feature/document-grounding-evaluation`의 합성 18건에서 실패 3, 허용 누락 7, 근거 위치 일치 2, 자동 오확정 관측 0. 실제 문서 일반화·서비스 통합은 미검증.
- 2026-09-29: 기존 linked worktree `E:/AgentFit/tmp/worktrees/paired-review-evaluation` 재사용, 기준 테스트 729건 통과. `feature/anchored-langextract-evaluation` 생성. 명세·계획 작성.
- 다음 행동: 속성 파싱 계약을 작은 합성 probe로 확인한 뒤 Task 1부터 테스트 우선 구현한다. 원문·키·모델 응답은 영속 기록하지 않는다.
