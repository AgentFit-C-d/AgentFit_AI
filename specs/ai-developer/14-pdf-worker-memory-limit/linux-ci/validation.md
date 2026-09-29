# 검증 기록

- Windows 개발 환경의 AI 서비스 전체 단위 테스트 546건과 `git diff --check` 통과.
- 로컬 Python 환경에는 YAML 파서가 없어 YAML 정적 파싱은 미실행이다. GitHub Actions가 실제 workflow를 읽고 실행하는지 push 후 확인한다.
- [첫 Ubuntu 24.04 CI 실행](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36514678746)은 전체 546건과 `pip check`를 통과했다.
- [전용 시험을 추가한 두 번째 실행](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36514836438)은 실제 Linux 자식 프로세스의 `test_child_cannot_commit_more_than_its_limit`를 `ok`로 기록했다. 전체 546건과 `pip check`도 통과했다.
- 이 결과는 Ubuntu 24.04 GitHub runner의 `RLIMIT_AS` 경로를 검증한다. 다른 Linux 배포·컨테이너 메모리 정책, 실제 배포 환경의 자원 한도는 아직 검증하지 않았다.
- CI는 Provider API 키를 받지 않으며 외부 문서 전송을 수행하지 않는다.
