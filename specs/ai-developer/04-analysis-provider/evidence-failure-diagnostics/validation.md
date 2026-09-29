# 최종 근거 실패 진단 검증

## 재현 결과

2026-09-29에 고정된 공개 Mealie·Immich 문서를 같은 Solar Pro 4 복구형 설정으로 다시 분석했다. 최초 평가 결과와 별개로, 이 두 문서는 이제 원인 조사에 사용한 튜닝 자료다. 원문·응답·Profile·키는 기록하지 않고 호출 단계·고정 오류 사유만 로컬 ignored `ai_service/tmp/public-evidence-diagnostics-20260929/`에 기록했다.

| 문서 | 최초 추출의 오류 | 마지막 수정 호출 결과 |
| --- | --- | --- |
| Mealie README | `project_name` AMBIGUOUS_QUOTE(7회), `deployment` CONTEXT_NOT_FOUND, `features` VALUE_NOT_IN_QUOTE | `project_name` VALUE_NOT_IN_QUOTE |
| Immich README | `project_name` QUOTE_NOT_IN_CONTEXT | `project_name` QUOTE_NOT_IN_CONTEXT |

두 건 모두 3회 호출 후 `INVALID_EVIDENCE`로 실패했다. 마지막 오류는 `project_name`의 근거 계약 위반이다. 최초 오류 목록은 실행마다 일부 달랐으므로 고정된 모델 동작으로 일반화하지 않는다. 현재 복구형 분석은 전체 Profile 투영이 성공하기 전에 어느 한 필드가 실패하면 안전한 부분 Profile 스냅샷을 얻지 못한다. 그래서 다른 필드가 검증 가능해도 `failed`가 된다. 이는 코드 경로로 확인한 실패 증폭 구조이며, 수정 후 품질 향상은 아직 검증되지 않았다.

## 변경과 검증

- `SolarAnalyzer`는 최종 투영·의미 수정 재투영 실패를 `field`, 허용된 `reason`, 범위가 검증된 숫자만 내부 진단에 기록한다. 공개 API·Profile·프롬프트·호출 예산은 그대로다.
- 공개 평가 CLI는 단계와 안전 오류만 파일에 남긴다. 허용 목록에 없는 상세·원문·모델 응답은 버린다.
- 가짜 Provider 회귀 테스트로 마지막 수정 실패와 의미 수정 실패, 임의 상세 필터링을 확인했다.
- 전체 AI 테스트 556건 통과, `git diff --check` 통과. 원격 CI는 push 후 확인한다.

## 후속 설계 제약

다음 단계는 개별 필드의 구조 검증 실패가 전체 후보를 버리지 않도록 하는 일반적 복구를 검토한다. 실패 필드를 자동 확정하거나 근거를 추측해 채우면 안 된다. 구조적으로 검증된 다른 필드도 의미 검토를 통과하지 못했다면 반드시 사용자 확인 상태로 내려야 한다. 새 독립 문서로 효과와 오확정을 재검증해야 한다.
