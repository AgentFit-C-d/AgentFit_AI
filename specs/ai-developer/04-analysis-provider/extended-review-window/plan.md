# 구현 계획

1. 실패 테스트: `--extended-review-window` 단독·간결 검토와의 조합을 거부하고, 허용 조합은 분석기 600초·필드 120초·의미 검토 16,384토큰을 전달한다. 기본 `--accuracy-first`는 300초다.
2. `SolarAnalyzer`의 opt-in 실험 상한을 600초까지 허용하고 평가 CLI에서 새 선택형 기한을 연결한다. 서비스 경로는 기존 60초를 유지한다.
3. 전체 테스트와 Campfire 실제 1건을 실행한다. 완성된 검토의 형식 오류에는 허용된 고정 사유만 평가 진단에 추가하고 회귀 테스트한다. 출력 원문·키·Profile을 기록하지 않고 plan/results/summary 숫자와 해시만 남긴다.
4. 결과를 validation에 기록하고 `feature/extended-review-window`를 push한 뒤 Linux CI를 확인한다. 성공 여부에 따라 5문서 확대 또는 검토 분할 설계를 결정한다.
