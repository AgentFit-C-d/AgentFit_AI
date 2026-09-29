# 구현 계획

1. `SolarAnalyzer._analyze`의 최초 core/features 요청을 내부 hook으로 분리한다. 기본 hook은 기존 순차 호출을 유지한다.
2. 복구형 분석기 opt-in에서만 `ThreadPoolExecutor(max_workers=2)`로 두 요청을 실행한다. 진단 call 슬롯을 선예약해 순서를 고정하고, 두 future를 모두 회수한 뒤 원래 예외를 전파한다.
3. 동시 진입 barrier와 실패 시 회수를 확인하는 테스트를 먼저 작성한다. 기본/opt-out의 요청 payload·Profile·호출 수가 바뀌지 않는지 검증한다.
4. 공개 평가 CLI 선택 옵션과 계획 기록을 추가한다. 단계별 시간은 이미 내부 진단에 있는 수치 중 원문 없는 숫자만 평가 결과에 노출한다.
5. 공개 튜닝 문서에서 실제 호출을 실행한다. 품질·지연 개선이 확인되지 않거나 오확정이 늘면 서비스 기본값을 유지한다.
6. 전체 테스트, diff check, feature 브랜치 push와 Linux CI를 확인한다.
