# 계획

1. 고정 사례와 단위 테스트를 먼저 작성한다.
2. 기존 Solar 전송/파서를 재사용하는 독립 도구를 구현한다.
3. 호출 전 계획 해시를 저장하고 32회 순차 실행한다.
4. 결과와 한계를 기록하고 테스트 후 feature/api-contract-probe를 push한다.

공식 참고: https://console.upstage.ai/api/chat (2026-09-26 확인)

## 관찰 후 후속 검증
32회 결과에서 schema-low 8/8, schema-none 7/8을 관찰했다. 이를 일반화하기 전에 기존 quote-extraction 6사례와 현재 채점 revision 2를 그대로 사용하여 none/low 각 6회를 비교한다. 프롬프트·정답·토큰 제한은 변경하지 않는다. 기존 실행 도구에 독립 실행 옵션만 추가한다. 실행 순서는 none 후 low이며 각 1회인 한계가 있다. 6/6 미달이면 전체 문서로 확대하지 않는다.
