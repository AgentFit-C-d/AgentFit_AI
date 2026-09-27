"""Frozen review-contract demonstrations for opt-in evaluation."""
REVIEW_EXAMPLES = """
출력 계약 예시. checkedFields는 확인한 필드 목록이며 오류 목록이 아니다. 없는 정보를 요구하지 않는다. 실제 출력에는 설명 없이 JSON만 쓴다. 아래 예시의 사실을 실제 문서에 적용하지 않는다.
[L1] 필수 기능은 댓글 작성과 북마크 추가다.
초안: features=[댓글 작성, 북마크 추가], 나머지 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[]}
[L1] 필수 기능은 댓글 작성과 북마크 추가다.
초안: 모든 필드 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[{"field":"features","kind":"missing","itemIndex":null,"evidenceLineIds":[1]}]}
[L1] 사용자는 표를 예매한다. 관리자는 예매를 취소한다.
초안: features=[표를 예매한다, 예매를 취소한다], 나머지 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[]}
[L1] 사용자는 표를 예매한다. 관리자는 예매를 취소한다.
초안: 모든 필드 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[{"field":"features","kind":"missing","itemIndex":null,"evidenceLineIds":[1]}]}
[L1] 외부 시스템 연결을 사용하지 않기로 했다.
초안: external_integrations=[], 나머지 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[]}
[L1] 외부 시스템 연결을 사용하지 않기로 했다.
초안: 모든 필드 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[{"field":"external_integrations","kind":"missing","itemIndex":null,"evidenceLineIds":[1]}]}
[L1] 개발 검증 도구는 Zephyr이며 제품 운영 모델은 아직 미정이다.
초안: 모든 필드 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[]}
[L1] Nebula는 채택하지 않는다. 운영 모델은 Helios로 확정했다.
초안: ai=[Helios], 나머지 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[]}
[L1] Nebula는 채택하지 않는다. 운영 모델은 Helios로 확정했다.
초안: 모든 필드 null
출력: {"checkedFields":["project_name","project_type","domain","frontend","backend","ai","database","deployment","features","external_integrations"],"issues":[{"field":"ai","kind":"missing","itemIndex":null,"evidenceLineIds":[1]}]}
"""
