# 검증 기록 (2026-09-29)

## 원인 조사

이전 공개 튜닝 `ORDER101`의 한 진단 실행에서 최초 core 11.4초와 features 6.4초가 순차 실행됐다. 수정 요청은 남은 22.2초를 사용한 뒤 전체 40초 기한에 도달했다. 요청 크기는 core 약 50KB, features 약 43KB, 수정 약 62KB였다. 따라서 관찰된 `PROVIDER_TIMEOUT`은 한 Provider 호출의 40초 초과가 아니라 **앞선 두 호출이 전체 기한을 소모한 결과**다. 기본 FastAPI Worker도 분석에 40초를 주고, HTTP 요청 전체 기한은 기본 60초다.

## 구현 및 공개 튜닝 관찰

`RecoverableSolarAnalyzer(parallel_first_pass=True)`에서만 두 최초 요청을 동시에 실행한다. 가짜 Provider barrier 테스트로 실제 중첩, 두 요청의 종료 후 오류 전파, 고정 진단 순서와 기본 순차 경로를 확인했다. `--parallel-first-pass` 평가 옵션은 실행 계획에 기록한다. 안전 평가 산출물에는 단계별 요청 바이트와 경과 시간만 추가한다.

이미 사용한 한국어 공개 README 5건을 문맥 선택지 옵션 없이 병렬 옵션만 켜고 실행했다. 로컬 무시 경로 `E:/AgentFit/tmp/korean-parallel-first-pass-20260929/`에 안전한 결과가 있다. `partition=tuning`, `score_version=public-evidence-v2`이다.

| 상태 | 일치 | 근거 오류 판정 | 누락 | 판정 불가 | 최대 경과 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 완전 0, 확인 필요 3, 실패 2 | 9 | 1 | 3 | 2 | 39.7초 |

`ORDER101`은 이번 실행에서 20.1초 만에 3호출을 끝냈으나 `INVALID_EVIDENCE`로 실패했다. `TodayWhere`는 core 18.5초·features 2.3초가 겹쳤어도 수정 21.2초를 더해 39.7초가 걸렸고 `INVALID_EVIDENCE`였다. `FestMoment`는 기존 `SENSITIVE_CONTENT` 사전 검사에서 모델 호출 전에 실패했다. 2026-09-29의 옵션 없는 순차 재실행은 완전/확인 필요/실패 0/3/2, 일치 7, 근거 오류 판정 0이었다. 서로 다른 확률적 모델 응답이므로 이번 수치를 병렬화의 인과 효과로 해석할 수 없다.

## 결정

병렬 첫 호출은 전체 기한의 여유를 늘릴 수 있지만, 5건에서 완전 통과가 없고 근거 오류 판정도 남았다. 서비스 기본값을 켜지 않는다. 실제 서비스 준비에는 근거의 의미 판단, 수정 실패 후 부분 확인 흐름, 독립 문서 검증과 Spring 확인 후 저장 연동이 더 필요하다. `release_gate_passed=false`를 유지한다.
