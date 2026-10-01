# 구현·실행 계획

1. `work/harness/b-evidence-selection-comparison/experiment.py`에 입력/payload·단위 선택 어댑터를 만든다.
   기존 B 분류 지시와 설정을 재사용하고 근거 지시 구간만 교체한다. 양쪽 user message 완전 일치를 테스트한다.
2. quote/unit 고정 응답으로 단위 선택 오류, 원래 B 판정과의 동등성, 정상 태그 기능 복구와
   Clean UI 잘못된 확정도 통과할 수 있는 위험을 회귀로 드러낸다. 기존 오확정을 숨기는 새 gate를 만들지 않는다.
3. 기존 CallGate/NvidiaAnalyzer/streaming/free validator를 재사용하는 freeze/live runner를 작성한다.
   provider 실패/무료 미확인/identity 변경/19번째 호출/재실행을 로컬에서 차단 검증한다.
4. 신규 및 전체 로컬 회귀, 최종 독립 검토 후 코드를 동결한다. 기존 입력·모델·gold 해시를 확인한다.
5. 무료 확인이 유효한 경우에만 Q9회→U9회 한 쌍 실행한다. 실행 중 동결 코드를 수정하지 않는다.
6. 동일 지표·분모, 핵심 두 사례·호출수·시간·원자료 보존을 보고한다. feature 브랜치 push 후 종료한다.

사용자의 이번 요청이 위 비교와 실행의 승인이다. 실제 모델 평가는 로컬 고정 응답 테스트와 구분한다.
