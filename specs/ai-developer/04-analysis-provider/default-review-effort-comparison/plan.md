# 구현 계획

1. `ai_service/tests/test_default_review_effort_comparison.py`에 의미 검토만 추론량 변경, 교차 순서, 실패 별도 집계, 안전 산출물 테스트를 작성하고 실패를 확인한다.
2. `ai_service/agentfit_ai/default_review_effort_comparison.py`에 SolarAnalyzer의 검토 호출만 덮어쓰는 실험 분석기와 기존 `run_case`를 재사용하는 짝 평가 CLI를 구현한다.
3. 관련·전체 단위 테스트를 통과시킨 뒤 품질 위험 사례 소집합을 먼저 실행한다. `low`가 오확정이나 검증 오류를 늘리면 전체 확대를 중단하고 이유를 기록한다.
4. 신호가 양호하면 기존 합성 20건을 교차 순서로 한 번씩 평가한다. 결과와 채택/보류 판단을 `validation.md`에 기록한다.
5. 변경 파일만 커밋하고 `feature/default-review-effort-comparison`을 push한다.
