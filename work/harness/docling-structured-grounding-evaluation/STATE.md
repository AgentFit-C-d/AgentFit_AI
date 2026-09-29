# 상태

- 상위 목표: AgentFit AI 분석을 실사용 가능한 수준으로 구현·검증한다. 계획과 구현 진행은 사용자에게 승인받았다.
- 현재 기능: 표준 Docling PDF 구조와 anchored LangExtract·결정적 규칙을 같은 근거 계약으로 평가한다.
- 기준: `feature/anchored-langextract-evaluation`의 튜닝 합성 18건은 완료 18/18, 오확정 0, 허용 누락 0, 위치 18/18이다. 실제 PDF의 구조 분석과 독립 평가, 기본 서비스 연결은 미완료다.
- 2026-09-29: 기존 worktree를 재사용해 `feature/docling-structured-grounding-evaluation` 생성. 이전 기능의 사용자가 만든 미추적 `work/harness/service-readiness/`는 보존한다.
- 다음 행동: 표준 Docling 설치·모델 자산 상태를 확인하고, 실패하는 구조·페이지 매핑 테스트부터 구현한다. 실제 PDF는 로컬 변환만 한다.
