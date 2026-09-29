# 검증 기록 (2026-09-29)

## 재현과 수정

기존 `public-evidence-v2`는 부분 정답 위치 외의 원문 구간에 정확한 같은 값을 인용해도 근거 오류로 판정했다. `DevConnect` 공개 README의 한 진단 실행에서 `frontend=Flutter` 제안과 근거 span 모두 `Flutter`를 포함했지만, 근거 위치가 부분 정답의 위치와 달랐다. 해당 구간의 의미 적합성은 부분 정답만으로 확인할 수 없어 `wrong_evidence`라고 단정할 수 없다.

`public-evidence-v3`는 정답 위치의 값 근거를 `matched`, 다른 위치의 정확한 값 근거를 `indeterminate`, 값 자체가 없는 근거를 `wrong_evidence`로 분리한다. 정답 위치와 다른 위치를 모두 인용했다면 일치를 우선한다. 배열 span 공유와 다대다 별칭 판정은 유지한다. 재현 테스트는 수정 전 실패하고 수정 후 통과했다. 이전 산출물과 v2 수치는 변경하지 않았다.

프로젝트 가상환경에서 전체 **581건 테스트**가 통과했고 `git diff --check`에 오류가 없었다.

## 공개 튜닝 재실행

이미 사용한 공개 한국어 README 5건을 기본 순차 분석기로 한 번 실행했다. 로컬 무시 경로 `E:/AgentFit/tmp/korean-public-evidence-v3-20260929/`에 안전한 결과가 있다. `partition=tuning`, `score_version=public-evidence-v3`이다.

| 완전 | 확인 필요 | 실패 | 일치 | 근거 오류 확정 | 누락 | 판정 불가 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 4 | 1 | 7 | 0 | 9 | 4 |

`FestMoment`는 여전히 `SENSITIVE_CONTENT` 사전 검사에서 실패했다. 최대 경과는 40.1초였다. 이 실행은 모델 출력도 새로 받았으므로 이전 v2 점수와 차이를 채점기만의 효과로 계산할 수 없다. 또한 판정 불가 4건은 사람 검토가 필요하며 품질 통과로 세지 않는다. `release_gate_passed=false`를 유지한다.
