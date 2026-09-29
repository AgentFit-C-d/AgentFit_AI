# Linux PDF Worker 실제 검증

## 목적

PDF Worker의 Linux `RLIMIT_AS` 경로는 Windows 개발 환경에서 모의 테스트만 통과했다. Ubuntu CI에서 실제 자식 프로세스 메모리 제한과 AI 서비스 전체 회귀 테스트를 실행한다.

## 계약

- GitHub Actions `ubuntu-24.04`, Python 3.13에서 `ai_service/requirements.txt`와 현재 검증 환경의 테스트 의존성 `httpx==0.28.1`을 설치한다.
- 외부 모델 API 키·문서 전송 없이 `unittest discover -s tests -q`와 `pip check`를 실행한다. 이 전체 테스트에 실제 자식 프로세스가 128 MiB 제한에서 256 MiB 할당을 거부하는 `test_worker_memory`가 포함된다.
- workflow는 push·pull_request·수동 실행에서 AI 코드나 workflow 변경 시 실행한다. 권한은 `contents: read`만 요청한다.
- CI 녹색은 Linux 테스트 통과의 증거이지만 실제 배포 환경 전체의 보안·성능 검증을 대체하지 않는다.

## 수용 기준

1. workflow 문법과 실행 명령을 검토하고 브랜치에 push한다.
2. 해당 브랜치의 GitHub Actions 실행이 완료되면 Linux 메모리 테스트와 전체 테스트 결과를 확인한다.
3. 실패 시 원인을 재현·수정하고 녹색 실행까지 확인한다. CI가 조직 설정으로 차단되면 설정 차단 사실을 기록한다.
