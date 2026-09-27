# 후보별 통합 판정 — 사용자 승인 완료
## 문제와 확인된 근거
기존 판정은 후보마다 field/role/status/scope/decision을 동시에 생성한다. selected 제약으로 상태 모순을 차단해도 동일27건 대조는15/27→15/27, 미정·미언급 오확정은 양쪽2건이었다.
원인이 출력 복잡도라고 입증된 것은 아니다. 다음 실험은 그 가설을 독립적으로 검증한다.

## 이전 접근과 차이
- section-decisions는 앞 추출기가 붙인 필드·역할·상태를 유지하고 selected/제외만 골랐다. 잘못된 선행 라벨을 수정할 수 없었다.
- independent-classification/factual-questions는 Jev로 여러 의미 축을 별도 질문했지만 오확정 관문을 통과하지 못했다.
- 이 제안은 분류 라벨 없는 원문 인용+위치focus에서 Solar가 최종 필드/채택 의미를 하나의 문자열로 고른다. 기존 라벨이나 정답을 입력하지 않는다.

## 대안과 선택
1. 기존5키에 설명/예시 추가: 변경은 작지만 이번 선택 제약에서도 의미 정확도 개선이 없었다.
2. 후보별 통합 판정(제안): 동시5축 출력의 모순 가능성과 출력량을 줄인다. 일부 제외 분류 정보와 충돌 검사 근거가 줄어드는 위험이 있다.
3. 축별 추가호출: 판단을 분리하지만6회/60초에서 추출·검토·수정 예산을 압박하고 기존 다축 질문 실험 실패도 있다.
이번 제안은2의 opt-in 비교이며 효과를 가정하지 않는다.

## 응답 계약
decisions의 공급된 모든 F ID에 문자열 하나를 반환한다. 누락·미지ID·중복JSON키·미지라벨을 거부한다.
- value:project_name, value:project_type, value:domain, value:frontend, value:backend, value:ai, value:database, value:deployment, value:features_user, value:features_operator, value:external_integrations
- absent:frontend, absent:backend, absent:ai, absent:features, absent:external_integrations
- omit
- conflict
총18개 라벨이다. 별도 selected/role/status/scope 값을 출력하지 않는다.

value 라벨은 해당 위치가 우리 현재 제품의 확정 사실이며 해당 필드의 정상 역할이라는 의미를 함께 가진다. 명시된 미래 요구는 미구현이어도 포함한다. features_user/operator는 기존 두 정상 역할을 보존한다.
absent 라벨은 현재 제품에서 해당 범주 전체를 사용하지 않기로 명시 확정한 근거다. 특정 제공자 거부나 미정은 해당하지 않는다.
omit은 개발전용·예시·다른제품·과거·거부·미정·무관·최종 사실의 중복 후보에 사용한다. 제외 사유의 세부 enum은 이 실험에서 제공하지 않는다.
conflict는 문서가 현재의 단일값 또는 존재/부재에 모순된 확정 사실을 제시하여 일관된 Profile을 구성할 수 없는 경우다. 하나라도 있으면 부분 Profile 없이 SEMANTIC_REJECTED로 실패한다.

## 서버 변환과 검증
서버는 모델이 고른 라벨을 표에 따라 기존 classify 입력으로 변환할 뿐 원문 의미를 재분류하지 않는다.
value→지정field/정상role/confirmed/current/selected.
absent→지정배열field/정상role/absent/current/selected; features 부재에는 기존허용 user_action 사용.
omit→단독irrelevant. conflict→명시적 실패.
최종 값은 기존 후보 quote 그대로이며 서버가 확인한 전역 span을 사용한다.
기존 classify/merge 검증의 선택 개수·중복값·선택된 스칼라 다중값·선택된 존재/부재 충돌·정확근거·미정 오확정 규칙을 우회하지 않는다. 중복을 서버에서 임의로 첫 위치로 정리하지 않는다.

## 충돌 검증의 차이와 위험
기존5키는 제외된 후보도 confirmed/current 등으로 분류돼 있으면 merge의 eligible pool에 들어가 충돌을 검출할 수 있다.
새 omit은 이 세부 분류를 잃으므로, 선택된 사실과 omit된 실제 확정 사실 사이의 충돌은 서버가 그 라벨만으로 탐지할 수 없다. 기존 모든 충돌 검증이 동등하게 유지된다고 주장하지 않는다.
모델의 conflict 판정 및 전체 원문 의미 검토로 보완하지만 누락될 수 있다. 실제 충돌을 omit으로 숨긴 실패를 별도 평가하며, 이 회귀가 발견되면 채택하지 않는다. 스키마 단순화를 위해 기존 보호를 조용히 완화하지 않는다.

## 범위·예산·전환
atomic_verdict=False 기본, v2와 candidate_occurrences=True에서만 opt-in 허용. selected_constraints와 동시 설정은 거부한다.
원문 후보 생성과focus는 이미 구현된 경로를 그대로 쓴다. 최초 판정·기존 후보 기반 재판정에 통합 판정을 사용한다. source_repair 계약과 검토는 변경하지 않는다.
새로운 호출·자동 재시도·모델교체 없음. 최대6회/60초, 원문24000자·후보120개, 공개Profile·Spring·저장정책 유지.
내부 의미 응답 계약과 제외 정보가 바뀌므로 사용자 지침의 주요 변경 확인 대상이다. 승인 전 서비스코드·API실험은 진행하지 않는다.

## 통과 기준과 제한
기존27건은 튜닝 자료다. 추가 충돌/중복 대조 자료를 실행 전에 고정한다. 양쪽 조건에 같은 원문·고정 후보·허용근거·정답을 적용한다.
구조 통과와 의미 정답, 잘못된 확정, 명시적 부재, 추출누락, 지연을 별도 측정한다. 어려운 사례를 제외하지 않는다.
독립 실제 기획서와 사용자 수정시간 검증은 여전히 필요하며 이 실험 성공으로 실사용 목표를 달성했다고 말하지 않는다. 예약 공개문서는 사용하지 않는다.
