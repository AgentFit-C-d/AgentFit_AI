# 구현 계획

1. 현재 메모리 제한 테스트·의존성·로컬 Linux 실행 환경을 확인한다.
2. 비밀 없이 Ubuntu CI를 작성하고 로컬 전체 테스트를 다시 실행한다.
3. `feature/linux-worker-ci`에 push한 뒤 실제 Actions run의 job·test 결과를 확인한다.
4. 실패하면 workflow나 Linux 구현을 수정하고 재실행한다. 검증 증거와 한계를 기록한다.
