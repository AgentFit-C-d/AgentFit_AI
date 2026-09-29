# 검증 기록

- Windows 개발 환경의 AI 서비스 전체 단위 테스트 546건과 `git diff --check` 통과.
- 로컬 Python 환경에는 YAML 파서가 없어 YAML 정적 파싱은 미실행이다. GitHub Actions가 실제 workflow를 읽고 실행하는지 push 후 확인한다.
- [첫 Ubuntu 24.04 CI 실행](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36514678746)은 전체 546건과 `pip check`를 통과했다. 메모리 제한 시험 이름을 로그에 직접 남기도록 전용 단계를 추가했으며 재실행 결과를 확인한다.
- CI는 Provider API 키를 받지 않으며 외부 문서 전송을 수행하지 않는다.
