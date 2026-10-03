# 역할 지침 명확화: 후속 소규모 비교안

상태: **계획만 작성, 미승인·미실행**. 큰 Goal paused. 기존 골드 수정0. 이번 문서의 합성 사례는 추가 테스트용이며 기존 실제 40개 의미 점수에 포함하지 않는다.

## 최소 수정 위치와 계약 영향

첫 변경 후보는 `ai_service/agentfit_ai/candidate_mention_roles.py`의 `MENTION_ROLE_INSTRUCTION` 하나다. 현재 역할 enum, field/schema, status/축 정의, `_decision`, 인용 방식, GLM 검토, confirmation-v3는 유지한다. `other`의 의미와 관계 판단을 명시하므로 새 데이터 모델이나 응답 계약은 필요 없다.

현재 이 상수의 제품 코드 소비자는 `candidate_semantic_assessment.py`다. GLM 분할 검토는 해당 상수를 사용하지 않는다. 추후 이 공유 상수를 실제 수정하면 semantic assessment를 쓰는 실행에 분류 결과 변화가 생길 수 있다. **첫 실험은 독립 평가 payload의 이 블록만 교체해 비교하고 서비스 적용은 별도 결정**한다. 서버 검증 완화나 field가 맞으면 역할을 무시하는 변경은 하지 않는다.

## 제안 문구 초안

아래는 기존 역할 지침 블록의 대체안이다. 제품명·문서 문장·후보 ID·정답 예시는 포함하지 않았다. 다른 system 블록은 그대로 둔다. 실제 실행 전 이 문구와 전체 요청의 해시를 고정하고 결과를 본 뒤 바꾸지 않는다.

```text
Identify what the exact candidate refers to in this occurrence before choosing its field.
Distinguish the identity of the target product, a fact about that product, an action,
a compatibility/configuration target, and an outside provider used by the product.
The grammatical subject of an action is not itself the action.

external_service refers to the named outside provider itself in an explicitly stated
integration relationship: the target product uses that provider's authentication,
data, communication, payment, or another concrete service. A supported client,
compatible platform, or configuration-output target alone does not establish this
relationship. A service can be used through an SDK; do not require deployment proof,
an API URL, or a particular implementation mechanism. A committed requirement can
establish the relationship before implementation. Use the existing dedicated field
definitions for operating AI models/APIs, implementation stacks, storage engines,
and deployment choices rather than treating every outside name as an integration.

product_operation is an explicitly stated action performed by the target product
or its users. A product name or a compatibility target's name alone is not an action.
role_description describes what a tool/provider is used for, not the provider name.
description is a modifier, benefit or tagline, not a named service or operation.
Read subject/action/provider relationships in sentences, lists and tables regardless
of order. Never copy the provider field onto its purpose. The purpose can support
a feature only when its context explicitly establishes a product operation;
otherwise preserve the relevant ambiguity as tentative.

mentionKind=other covers facts expressed by the remaining Profile fields, including
target product identity, delivery form, problem domain, implementation technology,
operating AI, storage engine, and deployment environment. These can be current
positive product facts: use their actual Profile field and role=product_fact when
supported. They are not automatically non_product or irrelevant. A noun phrase that
states delivery form or problem domain is not merely description for being descriptive.
mentionKind=other is distinct from field=other. The instruction about facts outside
the ten fields refers to field=other, not every use of mentionKind=other.

Judge every occurrence by its relationship and subject. A name mentioned in another
project or an example does not inherit target-project adoption. The same name may
be a compatibility target in one occurrence and a consumed provider in another.
Use field=other and irrelevant only when the claim is clearly outside all ten fields;
do not convert a bare target name into a feature. Preserve an explicit action in
features when that candidate and its context actually state the action.
Use unclear and tentative for unresolved relevant roles in a plausible field;
role uncertainty is not irrelevance. Preserve the existing scope, time, polarity,
commitment and status rules. Explicit denial stays negated in the corresponding
field; undecided adoption and unresolved conflicts must not become confirmed.
Select both sides of a genuine unresolved conflict, and keep unrelated denials
separate. Do not infer roles from capitalization, brands, name lists, or typical
capabilities. Do not generate user approval.
```

위 문구는 승인 전 초안이며 구현하거나 실행하지 않았다.

기대 효과는 대상 이름/유형의 external_service·product_operation 오분류 감소와 지원 Client의 잘못된 외부 연동 채택 감소다. **효과는 아직 미측정**이다. 기존 schema/server는 그대로이므로 잘못된 역할은 계속 보류한다.

정상 손실 위험: 실제 SDK 인증 연동을 단순 Client로 잘못 제외할 수 있다. 반대로 단순 호환성 지원을 ‘integration’으로 넓혀 해석할 수도 있다. 형태·도메인을 description으로 취급하거나 실제 외부 제공자까지 other로 바꾸는 위험도 있다. 따라서 정상 GitHub 보존과 기존 정상 other/project_type을 반드시 같은 주 비교에 둔다.

## 최소 실제 비교: 8개 발생 위치 × A/B 한 쌍

현재 요청을 재실행하는 승인이 아니다. 승인 후에만 다음을 시행한다.

- A: 현행 역할 지침. B: 위 대체 블록. 모델·모든 다른 지침·schema·서버·문맥·후보·정답 동일.
- 기존 DeepSeek `deepseek-ai/deepseek-v4.1-flash`만 사용. GLM, U/US, 새 추출/검토/복구 worker는 사용하지 않는다.
- v3 저장 후보의 아래 8개를 시작 위치 순서대로 **한 배치**로 사용한다. 양쪽 모두 같은 배열·ID·원문 위치를 사용한다. 원문 7,796 Unicode 문자 전체와 `_source_mention`의 앞뒤 최대 240자 및 원문 슬라이스를 똑같이 보낸다. 다른 자료나 정답을 모델에 보내지 않는다.
- 이전 저장 A 결과는 배치 구성이 다르므로 통제된 A 대신 사용하지 않는다. **최소 새 호출은 A 1회 + B 1회 = 2회**, 재시도0. 출력·추론·timeout 옵션은 동결한 기존 분류 요청과 동일하게 사용하고 옵션 오류 시 임의 변경하지 않는다.
- 요청당 최대600초, 전체 최대1,220초(20분20초, 종료 기록20초 확보). 매 요청은 전체 남은 시간에서 종료 여유를 뺀 값 이하로 제한한다. 첫 실패·무료 여부 미확인·한도 소진에서 후속 전송 중단. 유료 전환/대체0. 실행 시점에 승인된 무료 endpoint 범위를 다시 확인한다.

### 고정할 기대값 초안

기존 골드의 project_name/project_type/external_integrations 의미를 그대로 적용한다. mentionKind 기대는 기존 서버 역할 계약의 파생 기대이며 골드에 새 필드로 쓰지 않는다. 부정/미정/다른 프로젝트가 없는 아래 주 후보는 모두 사람이 판단할 수 있는 명확한 관계다.

| v3 후보 | 위치 | 원문 후보 | 기대 field / 역할 / 상태 | 근거 |
| --- | --- | --- | --- | --- |
| C000 | `[2,10)` | AgentFit | project_name / other / confirmed | 문서 제목 |
| C002 | `[137,142)` | 웹 서비스 | project_type / other / confirmed | 대상 서비스 한 줄 정의 |
| C003 | `[168,176)` | AgentFit | project_name / other / confirmed | 대상 제품 소개의 주어 |
| C043 | `[1857,1863)` | GitHub | external_integrations / external_service / confirmed | 로그인 흐름도 |
| C081 | `[3570,3576)` | GitHub | external_integrations / external_service / confirmed | 필수 로그인 범위 |
| C091 | `[4020,4025)` | Codex | field=other / irrelevant | 지원 Client라는 이름. 외부 제공자나 동작 자체를 명시하지 않음. mentionKind=other로 표현 가능 |
| C125 | `[5122,5128)` | GitHub | external_integrations / external_service / confirmed | GitHub 로그인, 저장소 권한은 별도 부정 |
| C145 | `[7266,7274)` | AgentFit | project_name / other / confirmed | 대상 제품 요약 |

이름3·유형1·인증3·범위 밖1 = 8개 발생 위치다. 독립 문서8개 또는 정상 의미7개로 부풀리지 않는다. 정상 **고유 의미는 이름·유형·GitHub 인증의 3개**, 범위 밖 Client 1개다. 각 발생 위치 결과와 고유 의미 단위 보존을 나눠 보고한다. 다른 발생 위치에서 정상 값이 보존되는지도 표시한다. 이 실험은 후보 분류만 검사하므로 최종 Profile의 실제 보존 점수를 만들지 않는다.

### 측정과 판정

1. 원시 역할/field/status와 scope/time/polarity/commitment/role을 보존한다. 의미상 오분류와 조합 불일치를 따로 표시한다.
2. **모델 오확정**: 실제 외부 서비스가 아닌 Client를 confirmed 유효 필드로 출력하는 등 원문 기대와 다른 긍정 사실. 역할만 틀린 정상 field는 역할 오류로 별도 계수하고 최종 오답과 합치지 않는다.
3. **서버 통과 오확정**: 잘못된 의미가 supported로 통과한 수. 모든 보류 방식으로 이 수만 줄이는 것을 성공으로 삼지 않는다.
4. **정상 보존/보류/제외·미응답**: 정상7발생 위치 각각의 결과를 분리하고 정상 고유 의미3개의 supported 근거 유무도 별도 집계한다. 보류를 정상 누락에 숨기지 않으며 raw 행 누락은 응답 계약 실패로 기록한다.
5. **올바른 제외**: Client의 field=other/irrelevant와 서버 제외. 애매한 후보를 일괄 other로 보내는 것을 개선으로 보지 않는다.
6. **인용 결함**: exact quote·occurrence 유효성 및 선택 후보 포함 여부를 별도 집계한다. GitHub 인용 오류 감소를 역할 지침의 의미 개선으로 단정하지 않는다.
7. **불확실성**: raw tentative인데 server excluded인 조합을 별도 보고한다. 이번 보완으로 서버의 proposed 정책까지 해결됐다고 주장하지 않는다.
8. 호출 수·호출별/전체 시간을 기록한다. 동일 성능의 단순 시간 변화는 모델 응답 변동을 포함한다.

방향성 인정의 최소 조건: Codex의 supported 오확정 감소, 정상 이름/유형의 역할 오류 감소, GitHub 정상 의미의 채택 손실 없음, 전부 보류 아님. 이를 충족해도 1쌍의 응답으로 재현성·다른 문서 일반화·최종 서비스 개선을 확정하지 않는다. 결과를 본 뒤 지침/정답을 바꾸지 않는다.

## 추가 대조 사례 — 기존 골드와 별도

아래는 **서버 규칙 검사에 사람이 지정한 응답을 넣는 합성 자료**다. 이름은 데이터 예시이며 제품 규칙에 하드코딩하지 않는다. 이러한 테스트가 통과한다고 모델이 실제로 관계를 구분한다고 해석하지 않는다.

| 구분 | 추가 문맥·후보 | 기대 / 현재 확인 수준 |
| --- | --- | --- |
| 대상/다른 프로젝트 | 대상 제품은 LumaDock. 비교 사례 EchoNote | LumaDock project_name/other supported. EchoNote scope=other 제외. 오프라인 통과 |
| 예시 프로젝트 | 사용자 입력 예시의 프로젝트명 EchoNote | 대상 이름으로 채택 금지, raw scope=other 유지. 오프라인 통과 |
| 같은 이름·다른 관계 | Kora용 설정 파일 출력 / Kora 인증 API로 신원 검증 | 앞 이름은 지원 대상으로 제외, 뒤 이름은 외부 연동 supported. 서로 다른 원문 위치 유지. 오프라인 통과 |
| 정상 인증·별도 부정 | GitHub 로그인, 저장소 권한 요청 없음 | 인증 연동 supported. 부정 대상이 저장소 권한임을 구별. 오프라인 통과 |
| 명시적 부정 | AtlasID 연동을 사용하지 않는다 | 해당 field, raw negated 보존, 긍정 값 제외. 오프라인 통과 |
| 미정 관계 | Kora 관련 지원 미정 | unclear/tentative 보류. 오프라인 통과 |
| 해결되지 않은 상충 | 같은 배포의 AtlasID 인증 제공 / 제공하지 않음, 미해결 | 두 근거 보존, needs_confirmation. 오프라인 통과 |
| 채택 검토 | AtlasID 연동 검토 중, 채택 미정 | raw tentative/proposed → 보류 기대지만 현재 excluded. **별도 예상 실패1건** |

다음 변형은 아직 모델 평가·자동 테스트하지 않은 **후속 대조 설계**다: 동일 역할을 다른 이름/언어로 교체, 제공자-동작 순서 반전, 표/목록/문장 간 변환, SDK를 통한 실제 인증, 배포 환경·운영 AI 모델 이름이 외부 연동이 아닌 전용 field로 가는 경우, “service”가 포함된 대상 제품명, 문서의 가상 예시에서 사용된 실제 유명 제품명. 문구 예외 없이 관계만 같으면 같은 판정을 기대한다. 애매한 지원 관계는 강제 제외 정답으로 만들지 않는다.

새 독립 문맥까지 실제 모델 일반화를 보려면 그 문서·후보·정답을 먼저 고정하고 별도 승인이 필요하다. 위 최소2호출 안에 추가 배치를 자동으로 끼우지 않는다.

## 필요한 승인 / 종료 조건

- 승인 범위: 제안 역할 지침 블록만 실험 payload에 적용, 동일 8후보의 무료 NVIDIA A/B 최대2회. 지금은 실행 승인 요청을 보내지 않고 계획을 보고한다.
- 제외 범위: 서버 proposed 처리 수정, schema/역할 enum 변경, GLM 검토 지침 수정, 서비스 상수의 실제 배포, 전체 문서 평가, 복구 재개, Spring 저장, 큰 Goal 재개.
- 승인 후에도 로컬 schema/서버 재현이 깨지면 실제 호출 전에 중단한다. 실제 호출 실패 후 수정·재시도하지 않는다. 결과만 보고하고 종료한다.
