# 제안 값 확인 질문 전달 계약

## 목적

선택형 Solar 복구 초안은 의미 검토가 끝나지 않은 `suggested` 값마다 `REVIEW_UNAVAILABLE` 질문을 붙인다. 현재 FastAPI 경계는 질문을 `unresolved` 필드에만 허용해 이 안전 장치를 502로 거절한다. 확인 필요 응답의 검증 규칙을 확장한다.

## 범위와 계약

- `suggested`는 근거가 검증된 비-null 값이며, 선택적으로 `REVIEW_UNAVAILABLE` 질문을 한 개 가질 수 있다. 이 질문은 저장 전 사용자 확인을 요구한다.
- `unresolved`는 null이며 기존과 같이 안전한 사유의 질문을 정확히 한 개 가져야 한다.
- `unknown`은 null이고 질문이 없어야 한다. 후속 UI에서 편집 가능한 상태다.
- 필드별 질문은 중복할 수 없고 `questionId`는 `confirm_<field>`로 고정한다. 임의 텍스트·원문·키는 전달하지 않는다.
- `needs_confirmation`은 Spring이 사용자 확인 전 저장하지 않아야 한다. 이 작업은 FastAPI 응답 검증만 변경하며 기본 Worker의 분석기 및 Spring 저장은 변경하지 않는다.

## 수용 기준

1. 검증된 `suggested` 값의 `REVIEW_UNAVAILABLE` 질문은 HTTP 200 `needs_confirmation`으로 그대로 전달된다.
2. `suggested`에 다른 사유를 붙이거나 `unknown`에 질문을 붙이면 안전 오류 502다.
3. 기존 `unresolved` 질문 필수 규칙과 기본 `complete` 응답은 유지한다.
4. 전체 단위 테스트를 통과하고 브랜치에 push한다.
