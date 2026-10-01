# 리뷰 지적 수정 및 확인 부담 처리

독립 리뷰 Important 3건을 수용했다. 수정은 한 번의 패스로 처리하고 회귀를 다시 실행한다.

1. 값마다 서버가 계산한 sourceValue/documentId와 정확한 지원 후보 span을 연결한다. 넓은 근거에 다른 값 삽입, 하나의 후보를 여러 값으로 분해하는 행위를 거부한다. 프로젝트명 병기는 기존 source_name_expression이 재현하는 원문 표현만 unresolved 상태로 허용한다.
2. 유효한 지지 근거·상충 검토 완료·상충 없음이며 other/non_product/irrelevant가 일치하는 항목은, 무관한 채택 축이 unclear라는 이유로 모든 필드를 확인시키지 않는다. 확정 허용 조건은 완화하지 않는다.
3. finish 당시 documentId/attemptId를 draftSource에 저장하고 승인 이력으로 복사한다. 현재 latestAttempt에서 과거 초안 출처를 추정하지 않는다.

추가로 `other`이면서 실제 확인이 필요한 후보 때문에 모든 10필드를 unresolved로 바꾸지 않는다. 해당 후보는 `modelDecisions`에 그대로 남기고 선택적 `unassignedQuestions=[{questionId: review_unassigned, candidateIds: [...]}]` 한 묶음에 모은다. 누락/숨김/외부 ID를 거부한다. 해당하는 필드가 있는 보류는 기존 필드 질문으로 유지한다. 사용자 승인은 여전히 별도 PATCH에서만 발생하며 질문 묶음이 자동 승인하지 않는다. 공개 OpenAPI는 변경하지 않는다.

질문 묶음 수와 실제 확인 후보 수를 함께 보고한다. 묶음 수 감소를 사람 검토량 감소로 주장하지 않는다. 기존 평가 출력/정답을 고치지 않고 고정 응답을 새 경계에 재생한 결과를 별도 저장한다.
