# 검토 계약 오류 진단

## 목표와 근거

실사용 가능한 분석을 막는 검토 실패의 원인을 판별한다. H02의 7d6f1b7 평가에서는 15호출 모두 전송 완료됐으나 GLM 5번째 후보 검토가 INVALID_REVIEW_CONTRACT로 실패했다. 어떤 조건을 위반했는지는 기존 기록으로 알 수 없다. 원문 응답을 보관하지 않았으므로 과거 실패의 정확한 원인은 미확인이다.

이번 변경은 기존 검토 함수의 제한된 관측 보완이다. 사용자 지침에 따라 specs에 SDD 문서를 남기고 직접 구현한다. 목표에 대한 설계·계획·구현 자율 승인을 적용한다.

## 계약

1. 선택형 `review_calls`의 각 새 행에 `contract_issue: str | None`을 추가한다. 성공 또는 응답 파싱·전송·모델 확인 단계에서 실패하면 None이다.
2. 기존 boolean 검증이 실패한 경우에만 고정된 진단 코드를 기록한다. 기존 검증 함수가 수락 여부의 유일한 기준이다. 예외 형식과 INVALID_REVIEW_CONTRACT 상위 코드를 유지한다.
3. 목록 진단은 고정 접두사 CHECKED_CANDIDATE_IDS, WRONG_CANDIDATE_IDS, CHECKED_FIELDS, MISSING_FIELDS와 고정 접미사 TYPE, MEMBER, DUPLICATE, MISSING, ORDER를 조합한다. TYPE은 목록 형식, MEMBER는 항목 형식/허용 집합 위반이다. MISSING/ORDER는 전체 목록에만 적용한다. 검사 순서는 TYPE→MEMBER→DUPLICATE→MISSING→ORDER다.
4. 반려 사유는 REJECTION_REASONS_TYPE, REJECTION_REASONS_COUNT, REJECTION_REASONS_ROW_SHAPE, REJECTION_REASONS_ID_MEMBER, REJECTION_REASONS_REASON_VALUE, REJECTION_REASONS_DUPLICATE_ID로 구분한다. 해당 순서로 검사하며 첫 위반만 기록한다. 다른 조건에 해당하지 않으면 UNKNOWN_REVIEW_CONTRACT다.
5. 후보 검토는 checked IDs→wrong IDs→reason rows 순서, 전체 근거 검토는 checked fields→missing fields 순서로 진단한다. 후보 ID, 필드 값, 인용, 잘못된 모델 문자열, 키 및 원문 응답은 추가 기록하지 않는다.
6. 진단은 입력과 기존 collector 행을 변경하지 않는다. collector가 없으면 진단을 실행하지 않는다. 기존 payload, 반환값, 모델, 예산 64회, NVIDIA 전송 재시도 1회 및 의미 실패 시 중단을 유지한다. JSON 파서가 먼저 거절한 응답은 INVALID_RESPONSE 등 기존 분류를 유지한다.

## 검증 및 실제 평가

- 합성 transport를 통해 실제 파서와 기존 검토 함수 전체를 실행한다. 목록·사유 오류의 구분, 이전 행 보존, 비밀 문자열 비노출, collector 유무의 요청/결과 동일성, 파서·전송 실패의 None, 통합 파이프라인의 조기 중단을 검증한다.
- 전체 unittest와 독립 코드 리뷰 후 구현 revision을 고정한다. 승인된 개인정보 제거 H02에 한 번 새 평가를 실행하며 이전 실행을 덮어쓰거나 재개하지 않는다.
- 실제 재발 시 고정 코드로 실패 조건을 확인한다. 재발하지 않으면 과거 원인이 해결됐다고 주장하지 않는다. 6개 부분 정답만으로 문서 전체 정확도를 주장하지 않는다.
- 기본 HTTP·공개 Profile·모델 프롬프트·의미 규칙은 이번 범위 밖이다. Spring 연동과 독립 문서 품질 기준은 전체 목표의 남은 요구사항이다.
