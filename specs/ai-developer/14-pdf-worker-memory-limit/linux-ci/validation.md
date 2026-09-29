# 검증 기록

- Windows 개발 환경의 AI 서비스 전체 단위 테스트 546건과 `git diff --check` 통과.
- 로컬 Python 환경에는 YAML 파서가 없어 YAML 정적 파싱은 미실행이다. GitHub Actions가 실제 workflow를 읽고 실행하는지 push 후 확인한다.
- Ubuntu CI의 실제 PDF Worker `RLIMIT_AS` 시험과 전체 테스트 결과는 아직 미확인이다. 녹색 run을 확인한 뒤 결과를 갱신한다.
- CI는 Provider API 키를 받지 않으며 외부 문서 전송을 수행하지 않는다.
