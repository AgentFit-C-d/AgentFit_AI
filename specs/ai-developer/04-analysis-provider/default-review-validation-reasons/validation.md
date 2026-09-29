# 기본 의미 검토 오류 사유 검증

2026-09-29, 기본 `SolarAnalyzer`의 내부 호출 진단과 합성 평가 산출물에 `REVIEW_INVALID_REASONS`의 고정 사유만 전달했다. 공개 오류 `SEMANTIC_REVIEW_INVALID`, Profile, Worker 설정 및 호출 수는 변경하지 않았다.

과거 형식 오류가 관찰된 사례를 제한 재실행했다.

| 실행 | 결과 |
| --- | --- |
| 기본 설정 N-002 | 완료·정답 일치 |
| 기본 설정 E06 | `INVALID_EVIDENCE` |
| 교차 재실행 N-002 medium/low | medium 완료·정답 일치 / low `SEMANTIC_REVIEW_INVALID` |
| 교차 재실행 N-003 medium/low | medium `SEMANTIC_REJECTED` / low `PROVIDER_TIMEOUT` |

재현된 N-002 low 형식 오류의 고정 사유는 **`ARRAY_INDEX`**였다. 이는 모델이 반환한 기존 배열 항목 이슈의 `itemIndex`가 현재 Profile 배열의 유효한 정수 인덱스가 아니어서 거부되었다는 뜻이다. 정확히 어떤 값이 나왔는지는 원본 응답을 저장하지 않아 알 수 없다. 기존 실행의 같은 오류가 이 사유였다고 소급 단정할 수 없다.

2쌍에서 low 완료 0/2, medium 완료 1/2로 이번에도 low 채택 근거가 없다. 원문·Profile·원본 응답·키는 평가 산출물에 저장하지 않았다. 결과는 로컬 `tmp/review-reason-default-20260929/`와 `tmp/review-reason-low-pair-20260929/`에 있다.

검증: 관련 테스트와 전체 단위 테스트 516건 통과. 다음 수정은 `ARRAY_INDEX`를 무시해 자동 완료시키는 방식으로 하지 않는다. 검토 프롬프트·스키마의 인덱스 표현 또는 해당 오류 시 확인 필요 처리안을 정확도와 시간 제한 조건에서 비교해야 한다.
