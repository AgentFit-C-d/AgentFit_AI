# run2 사전 기록

run1은 기존 배열 계약의 실패를 `ANCHORED_CANDIDATE`로만 기록해 승인된 명세의 원인별 지표를 충족하지 못했다. 원본 응답을 보존하지 않았으므로 과거 실패의 세부 원인을 추정하지 않는다.

run2는 동일한 합성 8건·Solar Pro4 설정·기존/신규 계약·교차 순서·8/8 및 27/27 관문을 사용한다. 유일한 코드 변경은 기존 실험용 `candidate_recall(..., diagnose=True)`가 실패 응답을 메모리에서 즉시 분류해 `id_coverage`, `wrong_unit`, `ambiguous_unit`, `not_in_source`, `duplicate_quote`, `invalid_quote`, `invalid_shape`, `other` 중 안전한 reason만 반환하는 것이다. 모델 입력, 프롬프트, 스키마, 검증 결과와 호출 예산은 바꾸지 않는다.

run1과 run2를 모두 공개하며 성능이 좋은 실행만 선택하지 않는다. 두 실행 모두 튜닝 합성 자료라 일반화·운영 적용의 근거는 아니다.
