# 구현·검증 계획

1. 기준 commit 10b8d02와 원본 fixture/서버/지침/계약 파일 해시를 별도 출력 폴더에 저장. 기존 복구 tests 실행을 재현해 실패와 무관한 통과를 구분.
2. 기존 복구 테스트 본문을 비자동수집 모듈로 이동하고 snapshot 환경에서 동일 본문 실행. 부모 suite는 자식의 각 결과를 개별 test로 수집. 선택된 코드 경로·hash, test ID 전체 집합·개수, network 차단을 확인.
3. 현재 코드에서는 실제 구 실행의 CODE_MISMATCH 및 옛 파생 decision 거부, immutable raw 재평가/별도저장 회귀 추가.
4. 격리 테스트의 결함 검사를 유효한 초기 상태에서 시작하게 하여 CODE_MISMATCH로 잘못 통과하지 않음을 확인. 조작된 자료는 임시 사본이며 원본 seal은 그대로.
5. 관련 tests → 전체 unit suite → 로컬 CI의 runtime/core-flow/contract tests. 보호 해시 재검증, 독립 코드 리뷰, 로컬 commit 후 결과 보고.

예산: 모델/외부전송0, 실제복구0. suite당600초, snapshot 자식180초. 로컬 목표2시간. 같은 실패가 반복되면 원인 조사로 돌아가며 테스트 기준을 낮추지 않는다. 이미 승인된 작은 테스트 구성 변경이므로 재승인을 요청하지 않는다. 기존 feature 브랜치 관례를 따라 feature/recovery-test-version-isolation, 외부전송 금지로 push하지 않는다.
