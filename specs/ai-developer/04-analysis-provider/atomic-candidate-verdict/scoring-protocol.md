# 충돌 대조 자료 사전 채점
counterexamples.json의6건은 개발 중 작성한 합성 튜닝 자료다. 실제 고객 문서나 최종검증 자료가 아니다. 기존27건 파일 해시를 함께 고정했다.

## 일반 Profile 네 사례
AC03은 두 동일 DB 위치 중 한 곳의 근거만 허용한다. 두 위치를 모두 반환하거나 첫 위치를 서버에서 임의로 선택하면 통과로 보정하지 않는다.
AC04·AC05는 현재 운영 모델 위치만 허용하며 과거·예시 위치는 실패다.
AC06은 모든 필드null/근거없음이다. 개발 도구 채택이나 범주 전체 부재로의 오확정은 실패다.
기존 score_profile과 전체 근거 대안 채점을 동시에 충족해야 한다.

## 충돌 두 사례
AC01은 동시에 유효한 단일 DB 두 값, AC02는 동시에 유효한 AI 채택/범주 전체 부재다. 임의 하나 선택이나 조용한 전체null은 정답이 아니다.
일반 예외 코드만으로 충돌 정답을 인정하지 않는다. 유효한 모델 응답이 공급된 충돌 후보들을 명시적으로 conflict로 판정했는지를 먼저 검사한다.
- 기존5키: conflict_candidate_ids의 모든 후보가 정확한 conflict_field·current·정상역할과 expected status(AC01둘confirmed, AC02첫confirmed/둘째absent)를 가지고 decision=conflict여야 한다.
- 신규18라벨: conflict_candidate_ids의 모든 후보가 conflict여야 한다.
- 다른 후보/필드 선택이나 잘못된 키/enum/유실ID가 있으면 실패다.
- 조건을 만족한 명시적 충돌은 별도 conflict_recognized로 집계한다. Profile 반환 성공률에 섞지 않는다.
- SECTION_MERGE/SEMANTIC_REJECTED/timeout이라는 코드만 맞는 경우는 정답이 아니다.
이 규칙은 응답을 로컬 채점할 때만 사용한다. 정답 필드·후보ID·상태·허용근거는 모델 입력으로 보내지 않는다.
기존 통합기가 all-conflict 입력에서 모든값null을 만들더라도, 판정 원본의 명시적 충돌 인식을 채점하는 이 고정후보 평가에서는 구분한다. 전체 서비스의 오류처리가 같다고 주장하지 않는다.

## 실행 전 고정
두 조건에 같은 문서·고정 후보·focus를 제공한다. API 실험과 신규 응답 계약 구현은 설계 승인 전 수행하지 않는다.
