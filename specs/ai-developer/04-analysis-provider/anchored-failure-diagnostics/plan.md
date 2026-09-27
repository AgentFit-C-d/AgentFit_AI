# 계획
1. 선택 자격 오류, 중복, 충돌을 구별하는 회귀 테스트 작성.
2. merge_profile의 기존 거절 조건에 reason만 추가하고 Anchored 진단으로 전달.
3. 전체 테스트 후 합성6건의 후보·판단 probe 실행.
4. 의미 골드를 유지하여 후보에서 각 동작이 독립적으로 존재하는지 진단.
5. 구체적 수정 가설을 기록하고 push.

## 진단 후 단일 변수 후속 비교
기준 probe의 후보 span을 그대로 고정하여 원문에서 재구성한다.
판단만 none→low로 변경하고 모델/프롬프트/스키마/후보/4096토큰을 유지한다.
6건 각각1회. 검토는 실행하지 않으며 Profile 전체 품질 통과로 집계하지 않는다.
사전 판단 기준: Q001 features/current/confirmed/user_action 선택,
Q002 두 features/current/confirmed 각각 user_action/operational_action 선택,
Q003 선택 없음, Q004 external_integrations/current/absent/named_service 선택,
Q005 선택 없음, Q006 features/current/confirmed/user_action 선택.
Q001/Q006은 분류가 맞아도 후보 범위 오류가 남을 수 있다.

## 응답 형식 단일 변수 비교
복잡한 anyOf 구조가 분류에 영향을 주는지 검증한다.
기준 probe와 같은 후보·판단 프롬프트·추론none·4096토큰을 유지한다.
response_format만 json_schema에서 json_object로 바꾼다.
동일 classify 검증을 통과해야 하며 문서6개 사전 판단 기준은 위와 같다.
응답 형식이 결과를 바꾸더라도 1회 관측만으로 일반적 모델 성능을 단정하지 않는다.

### 실행 전 비교 조건 보정
기존 프롬프트는 루트 decisions와 모든 열거값을 설명하지 않는다.
json_object만 출력 계약을 모르는 비교를 피하기 위해 두 방식에 같은 명시적 JSON 계약을 추가했다.
각6건 비교군 간 차이는 response_format뿐이다. 과거 probe와의 차이에는 계약 설명 추가도 있으므로 형식만의 효과로 해석하지 않는다.
