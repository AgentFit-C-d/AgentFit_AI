# 로컬 전송 검증 보완

## 관찰과 한계

- 첫 전체 실행: 1043개 중 압축 응답 검증 1실패, 5skip. 다음 단독 전체 실행은 1038통과/5skip이었다.
- 실제 모델 실험 종료 후 task-done: 1043개 중 전송 테스트 5실패/5skip, 46.486초. 기대한 redirect/encoding/network/size 오류보다 부모의 PROVIDER_TIMEOUT이 먼저 발생했다. 이 실행은 작업 완료로 기록하지 않았다.
- 별도 루프백 계측 12회: 모두 기대 오류로 종료, 0.296~0.444초. worker import, TLS context 생성, opener 생성, 실제 서버 요청, 응답 종료를 구분했다. 외부 API·실제 키·문서는 사용하지 않았다.
- 전체 테스트 계측 1회: 1038통과/5skip, 29.772초. 부모 호출 30건 중 느린 응답 검증 4건이 서버 요청 도착 전에 timeout으로 종료됐다. 즉 기존 테스트의 성공이 실제 응답 중단을 입증하지 못했다.
- 계측 실행의 바깥 PowerShell exit 구문은 quoting 오류로 exit1이었다. 테스트 runner의 결과와 JSON 요약은 정상 기록됐지만, 이 실행을 최종 gate로 사용하지 않는다.
- 앞선 간헐 지연의 환경 원인은 재현하지 못했다. 이번 보완으로 그 원인이 해결됐다고 주장하지 않는다.

## 보완 범위

제품 코드, 제품 timeout, 재시도, 모델 결과는 변경하지 않았다. 테스트의 목적을 분리했다.

1. 프로토콜 오류 검증에는 로컬 자식 프로세스 시작을 포함한 10초 예산을 준다. 응답의 오류 종류와 내용 보존·비노출·재시도 없음 조건을 유지한다.
2. 실제 느린 응답 검증에는 5초 예산을 주고, 응답이 그보다 길게 지속되게 한다. 서버가 응답 전송을 시작한 Event와 6.5초 이내 종료를 모두 검사한다. 시작 전에 종료되면 통과할 수 없다.
3. 0.25/0.35초 요청 제한이 부모 subprocess와 자식 입력에 그대로 전달되고, timeout 오류가 안전한 코드로 반환되는지 별도 경계 테스트로 확인한다. 이 테스트는 실제 시간 측정의 대체가 아니다.

기존 짧은 시간에 Event assertion만 추가했을 때 NVIDIA 2 subcase와 Solar 2 test가 모두 RED였다. 테스트 입력 시간을 보완한 뒤 focused와 전체 gate를 확인한다. 변경된 테스트는 기존 제품 계약을 검증하므로 제품의 기능 추가를 주장하지 않는다.

## 증거 위치

- 로컬 계측기: `E:/AgentFit/tmp/probe-worker-startup-v1.py`, `probe-transport-suite-v1.py`
- 보존 실패 로그: `.superpowers/sdd/plan-review-batch-size/tests-initial-failure.log`, `tests-task-done-timeouts.log`
- 전체 계측: 같은 디렉터리의 `transport-suite-timing.log`, `transport-suite-timing.json`
- 최종 검증: 같은 디렉터리의 `task-1-tests.log`, `tests.log`; 완료 기록은 `progress.md`

이 자료는 모델 정확도 개선 증거가 아니다. 실제 H02 14/16, 부분 6/6, needs_confirmation 결과와 해당 한계는 기존 validation.md에 유지한다.

## 최종 로컬 검증

- NVIDIA 전송: 20/20, 16.825초.
- Solar 전송·분석: 23/23, 19.777초.
- task-done 전체: 1045개 중 1040통과, 기존 5skip, 49.667초.
- 설치된 SDK 경로: 4/4, 0.071초.
- `git diff --check`: 통과. LF/CRLF 알림은 기존 Windows Git 설정에 따른 알림이다.

이 gate는 테스트 보완 working tree에서 실행됐고 이후 커밋은 그 검증한 파일을 기록한다. 제품 코드와 실제 H02 결과를 다시 생성하지 않았다.
