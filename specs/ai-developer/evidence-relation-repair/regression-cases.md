# 회귀 테스트 계획과 새 문맥 대조 사례

**아직 테스트를 구현·실행하지 않았다.** 아래 새 문맥은 작성한 합성 문서이며 모델이 읽은 적 없는
별도 공개 문서 평가 결과가 아니다. 합성 기대값은 사람 검토 전 초안이다.
기존 승인10개 정답은 그대로 유지한다. 사례 ID와 아래 가상의 이름은 fixture 식별/입력용이며
분류 규칙·prompt 예외·이름 목록으로 사용하지 않는다.

## 검증 층 구분

1. 원문 위치 검사: 서버에서 결정적으로 검사할 수 있는 문자·offset·hash·후보 보존.
2. 고정 응답 계약 검사: 사람이 작성한 관계 assertion을 넣고 서버가 모순/보류/유효 주장을 처리하는지 검사.
3. 의미 정답 대조: 잘못된 고정 assertion이 형식상 통과해도 채점기는 오확정으로 센다.
4. 실제 모델 검사: 이번에 실행하지 않는다. 1–3 통과를4의 정확도 개선으로 표시하지 않는다.

## E. 근거 위치·인용 오류

아래 문자열의 `\n`, `\r\n`, `\t`는 미래 fixture에서 실제 제어문자로 해석한다.
후보 위치는 지정한 원문 문자열과 occurrence로 fixture 작성 시 계산·고정하며, 테스트 대상 코드가 재검색하게 하지 않는다.

| ID / 테스트명 | 입력·대조 | 기대 검증 |
| --- | --- | --- |
| E01 heading_only_is_not_candidate_support | `## 이번 릴리스 기능\n- 일정표를 CSV로 내보낸다.\n- 차분하고 세련된 화면.` 후보 각각 `일정표를 CSV로 내보낸다`, `차분하고 세련된 화면`; 잘못된 모델 quote는 제목뿐 | 두 후보의 mentionSpan은 복구해도 기존 보류를 승격하지 않음. 첫 문장은 정상 동작, 둘째는 설명이라는 의미 차이를 위치 검사로 덮지 않음 |
| E02 preserves_multiline_source | `### 준비 사항\n- Oriole 2.7\n- Finch 도구` 후보 Oriole 2.7. 오류 quote=`### 준비 사항 - Oriole 2.7` | 원문에 없는 줄바꿈 접기는 quote_not_found. 서버 source pointer/줄 단위는 원문 그대로. 이 위치 복구만으로 backend 확정 금지 |
| E03 keeps_the_selected_occurrence | `구형 Boreal은 Lumen 서비스를 사용했다.\n현재 Cedar는 Lumen 서비스를 사용하지 않는다.` 후보는 두 번째 Lumen | 첫 번째 근거로 두 번째 후보를 확정할 수 없음. 해당 occurrence를 포함하는 두 번째 문장/부정 보존. 순서를 바꿔도 명시한 대상·시점별 판단 유지 |
| E04 does_not_unescape_or_normalize | `![화면](/img/cedar.png?view=true "샘플")`를 모델이 `&quot;샘플&quot;`로 인용하는 오류와, 실제 원문에 문자 그대로 `&quot;`가 있는 정상 대조 | 두 원문을 각각 다르게 취급. 유사 인용을 원문 일치로 만들지 않음. 주어진 offset으로 원문 자체는 정확히 표시 |
| E05 unicode_crlf_and_spanning_candidate | `🚀 기능\r\n- 사용자별\t알림을\r\n  묶어 전송한다.` 후보가 두 줄을 가로지름 | UTF-16/byte offset과 혼동하지 않고 Python code point 기준으로 동일 value. 서로 인접한 단위의 범위가 후보 전체를 덮음. 공백 합성 없음 |
| E06 table_cell_has_its_own_context | `용도 \| 대상\n호환 브라우저 \| Aurora\n외부 검사 서비스 \| Aurora`에서 각 Aurora를 독립 후보로 제공 | 헤더와 각 행 참조를 별도 보존. 같은 값이라는 이유로 두 행의 관계를 합치지 않음 |
| E07 no_first_match_fallback | `알림을 보낸다.\n승인 후 알림을 보낸다.`에서 두 번째 `알림을 보낸다` 후보, 모델은 occurrence0 반환 | exact_elsewhere. 현재 후보 위치가 정상이어도 그 quote를 사용자가/모델이 선택한 근거처럼 소급 교체하지 않음 |
| E08 remote_negation_remains_visible | 도입부 `Cedar는 ParcelCloud를 검토한다.` 뒤에 중립 텍스트300자, 마지막 `이번 릴리스에서는 ParcelCloud를 사용하지 않기로 확정했다.` | 앞뒤240자 밖의 결정도 전체 원문/단위 목록에 존재. 앞부분만 선택된 경우 의미 확인 완료로 표시 금지. 로컬 단위 검사는 이 결정을 자동 이해했다고 주장하지 않음 |
| E09 recovered_anchor_does_not_promote | 실제 저장 B C004/C005 및 E01의 두 후보에 기존 confirmed와 후보 위치를 함께 주입 | original field/status/verdict 불변. 잘못된 설명 문구를 승격시키는 구현은 반드시 실패. 원래 정상 Internet Archive supported는 유지 |
| E10 corrupt_or_incomplete_source | 원문 한 글자 변경, 음수/end초과 위치, 중복 ID, 없는 unitId, source24001자, unit1001개, 선택9개·4001자 | 명시적 오류/불완전 문맥. 모델/API 자동 fallback 없음. 원래 후보 유실·부분 성공 위장 없음 |

## S. 지원 플랫폼·프로토콜·외부 서비스의 관계

여기서 '허용'은 조건이 맞는 **외부 연동 제안**이고 사용자 확정이 아니다.
거절은 해당 external_integrations 주장만 대상으로 하며 후보 삭제가 아니다.
표의 정상/오류 대조는 동일 relation 계약으로 검사한다. 예시 문장 외의 상식을 추가하지 않는다.

### S01–S04: 객체 종류와 방향

| ID | 새 문맥과 검사 후보 | 기대 관계 / gate |
| --- | --- | --- |
| S01a | `현재 Cedar 노트 앱의 확장 기능은 Aurora 브라우저에서 동작한다.` 후보 Aurora | supported_platform / 외부 연동 주장 거절 |
| S01b | `현재 Cedar 노트 앱은 Aurora라는 외부 웹 검사 서비스의 API에 주소 검사를 요청한다.` 후보 Aurora | consumes_service / 허용. 동일 이름이어도 S01a와 반대로 판정 |
| S02a | `현행 Cedar 로그인은 Beacon 인증 프로토콜을 준수한다.` 후보 Beacon | uses_protocol / 제공자 주장 거절 |
| S02b | `현행 Cedar 로그인은 Beacon이라는 외부 인증 서비스에 사용자 인증을 요청한다.` 후보 Beacon | consumes_service / 허용. 규약이라는 이름 사전 사용 금지 |
| S03 | `현재 Cedar는 외부 인증 사업자 KestrelCloud에 Lumi 규약으로 로그인을 요청한다.` 후보 KestrelCloud, Lumi 각각 | 전자는 consumes_service/허용, 후자는 uses_protocol/거절. 제공자와 규약이 한 문장에 함께 있어도 분리 |
| S04a | `현재 Cedar의 영수증 전달은 외부 알림 서비스 ParcelCloud의 전송 API를 사용한다.` 후보 ParcelCloud | consumes_service / 허용 |
| S04b | `ParcelCloud는 외부 알림 서비스다. 그 전송 API로 영수증을 보내도록 현재 Cedar에 채택했다.` 같은 후보 | S04a와 같은 결과. 객체가 먼저 나와도 주어/관계 방향 유지 |

### S05–S09: 설명·서술 순서·범위·불확실성

| ID | 새 문맥과 검사 후보 | 기대 관계 / gate |
| --- | --- | --- |
| S05a | `문서의 도구 설명 표: 공급자 ParcelCloud / 용도 영수증 전달. 대상 앱의 도입 여부는 미정이다.` 후보 ParcelCloud, 영수증 전달 | 제공자 후보도 채택은 보류. 용도 문구는 외부 제공자 아님. 설명만으로 실제 기능 자동 생성 금지 |
| S05b | `현재 Cedar는 사용자가 결제하면 ParcelCloud API로 영수증을 전송한다.` 후보 ParcelCloud, 영수증을 전송한다 | 제공자는 consumes_service/허용. 명시된 동작은 features로 유지하며 외부 주장 gate 대상 아님 |
| S05c | `Payments는 이 문서에서 외부 청구 서비스의 이름이다. 현재 Cedar는 Payments API로 청구한다.` 후보 두 번째 Payments | 이름이 일반 행동어여도 consumes_service/허용. S05a의 설명 문구와 이름 자체를 구분 |
| S06a | `대상 \| 관계\nAurora 브라우저 \| 현재 Cedar 확장 실행\nParcelCloud 서비스 \| 현재 Cedar 영수증 전송 API 호출` | 전자는 플랫폼, 후자는 서비스. 행별 근거 |
| S06b | S06a의 열 순서와 두 행 순서를 각각 뒤집음 | 의미와 기대 결과 불변. offset/unitId만 새 원문에 맞게 계산 |
| S07a | `구형 Boreal은 ParcelCloud를 사용했다. 현재 Cedar의 연동은 정하지 않았다.` 후보 ParcelCloud | 다른 프로젝트·과거 사실로 현재 외부 주장 거절. 제공자가 실재하는 듯 보인다는 이유로 현재 채택 전이 금지 |
| S07b | `이 예제의 가상 앱은 ParcelCloud를 호출한다. 현재 Cedar의 결정은 미정이다.` | 예시를 현재 제품 결정으로 확정하지 않음 |
| S08a | `현재 Cedar에 ParcelCloud 연동을 검토한다.` | proposed / 보류 |
| S08b | `현재 Cedar는 ParcelCloud를 사용하지 않기로 결정했다.` | negated / 해당 외부 주장 거절 |
| S08c | `현재 릴리스는 ParcelCloud를 채택했다. 동일한 현재 릴리스는 ParcelCloud를 사용하지 않는다.` | 어느 문장이 우선인지 없음: 상충 근거 양쪽 보존, 보류 |
| S08d | `초기 검토: ParcelCloud를 쓰지 않는 안. 최신 확정: 현재 Cedar는 ParcelCloud API를 사용한다.` 각각의 occurrence | 초기 검토는 현재 확정으로 전이하지 않음. 최신 candidate는 명시적 개정 문맥을 함께 남긴 경우 허용. 이전 문장과 같은 시점의 모순으로 취급하지 않음 |
| S09 | `현재 Cedar는 Halo 연동을 지원한다.` 후보 Halo. Halo가 플랫폼/규약/서비스인지 추가 설명 없음 | unclear / 보류. 임의로 제외하거나 서비스로 확정하지 않음 |

### S10–S14: 정상 정보 보호 및 평가기 한계

| ID | 입력·대조 | 기대 검증 |
| --- | --- | --- |
| S10 | `현재 서비스 이름은 Cedar다. 서버는 Wren 프레임워크로 구현하며 화면은 Spruce 언어로 작성한다.` 후보 Cedar/Wren/Spruce, 올바른 project_name/backend/frontend 제안 | external gate는 not_applicable. 외부 서비스 역할 enum을 요구해서 정상 기술을 보류하지 않음 |
| S11 | `현재 Cedar는 외부 보관 서비스 HavenVault에 문서 사본을 업로드한다.` 및 기존 Internet Archive | 정상 서비스는 허용. 모든 후보 보류/모든 연동 거절 구현을 걸러내는 positive control |
| S12 | 기존 승인 PWA 및 `현재 Cedar는 설치 가능한 웹 앱이다.`의 제공 형태 후보 | project_type 기준 유지. 이 관계 gate가 PWA 오류까지 해결했다고 계산하지 않음. 기존 틀린 features 출력은 계속 오류로 남음 |
| S13 | S01–S06의 이름을 새 가상 이름으로 치환하고 후보 ID를 전부 재배열, 조사·한영 표현을 바꾼 짝 | 의미상 같은 관계면 같은 결과. 이름/ID/위치 고정값 조건이 있으면 실패. 문맥에서 관계를 바꾼 경우에는 결과도 달라져야 함 |
| S14 | S01a의 원문에, 모든 참조가 유효하지만 relation=consumes_service라고 잘못 주장하는 mock을 주입 | 형식 gate만으로 의미가 보장되지 않음을 드러냄. 통과한 경우에도 독립 정답 채점기는 오확정1로 계산. 외부 서비스 모델의 실측 개선으로 보고 금지 |

## 동일 분모와 합격 조건 계획

- 저장 결과 baseline: 승인10개/양성6개와 전체68개 분모 유지. 신규 사례는 독립 partition.
- 로컬 anchor 단계: 후보 보존68/68, 원문 identity 보존, 원래 판정 변경0.
- 고정 관계 계약: 명확한 platform/protocol 주장 거절, 실제 서비스 허용, 불명확·상충 보류,
  정상 다른 필드 보존. 이 조건의1건이라도 위반하면 계약 테스트 실패.
- 의미 평가: 정상례의 누락과 보류를 별도 집계한다. all-held/all-rejected는 정상례에서 실패해야 한다.
- 추후 실제 모델 검증 전 사람이 새 gold를 확인한다. 검토 필요 사례를 맞춘 것으로 계산하지 않는다.
- 새 문맥 test가 통과해도 실제 모델의 일반화 근거로 쓰지 않는다. 실제 모델은 이번 **미실행**이다.
