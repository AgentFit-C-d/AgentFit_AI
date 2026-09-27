# 필드·역할 조건부 스키마

관찰: features+product_fact, frontend+user_action 등 잘못된 조합이 평평한 스키마를 통과한다.
독립 quote 평가기에 opt-in field-role 스키마를 추가한다. 공개 Profile/기본 서비스/프롬프트/정답 유지.
각 필드의 ROLES 및 제외 역할(development_task, technical_description, client, generic_source)만 허용한다.
명시적 부재는 배열 필드와 해당 필드 역할에만 허용한다. 다른 상태/스코프 의미 판단을 서버가 추정하지 않는다.
서버도 같은 조합을 확인하고 불일치 시 실패한다. 스키마 준수가 올바른 의미를 보증하지 않는다.
Mini4/Pro4 고정6사례 각1회. 앞선 동일 flat 평가와 비교하며 시간/반복 변동을 명시한다.
