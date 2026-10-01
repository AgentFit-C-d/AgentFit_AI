# 외부 연동의 의미 관계 검증 계획안

> 이후 구현을 승인받으면 superpowers:executing-plans로 직접 실행한다.
> B 추가 반복과 서비스 연결을 포함하지 않는다. 이번에는 설계·회귀 계획만 전달한다.

**Goal:** 외부 서비스 주장과 지원 플랫폼·프로토콜을 문장 속 관계로 구분하며 정상 외부 연동을 유지한다.
**Architecture:** 모든 필드의 역할을 다시 분류하는 대신, 외부 연동 주장에 한정된 relation 검증기를 준비한다.
원문에 묶인 관계 assertion을 읽고 형식/일관성을 검증한다. 원문 의미의 실제 판별은 별도로 검증해야 한다.
**Tech Stack:** Python/unittest/고정 JSON, 외부 호출 없음.
**Spec:** [spec.md](spec.md) B절. **사례:** [regression-cases.md](regression-cases.md) S01–S14.

## Global Constraints

- 모델/API 호출0, 재시도0, 서비스/공개 Profile/사용자 확인/Spring 변경0.
- 이름·브랜드·후보/문서 ID·URL allowlist/denylist 금지. 문서상의 관계와 해당 occurrence만 사용.
- sourceDigest·근거 단위는 evidence-plan E1 계약. 모델의 관계 출력은 검증 대상인 주장이다.
- 기존 승인10개 gold 불변. 새 합성 사례/관계 annotation은 사람 검토 전까지 draft.
- 새로운 관계 결과가 없는 과거 응답에는 `relation_not_assessed`를 기록한다. 사람/에이전트 정답을
  과거 모델 출력처럼 채워 넣거나 새 모델 성능으로 보고하지 않는다.

## 파일과 인터페이스

| 미래 파일 | 책임 |
| --- | --- |
| work/harness/evidence-relation-repair/relation_contract.py | 참조에 묶인 RelationAssessment와 외부 주장 gate |
| work/harness/evidence-relation-repair/relation_prompt.md | 이름 중립적 관계 질문·반대 근거 지시 초안, 전송하지 않음 |
| work/harness/evidence-relation-repair/offline_report.py | 저장 응답/고정 assertion/미측정 결과 구분 |
| ai_service/tests/test_external_relation_contract.py | 정상·오류·불명확·관계 위조 대조 |
| ai_service/tests/test_evidence_relation_replay.py | 원래 지표 보존과 잘못된 mock 의미 판단 탐지 |

## Task S1: 검토용 관계 사례와 정답 고정

**Consumes:** 승인 gold10개, source/raw hashes, 회귀 사례 문서의 완전한 합성 문장.
**Produces:** 미래 `specs/ai-developer/evidence-relation-repair/regression-fixtures.json`.
각 행: caseId/document/candidate spans/proposedField/expectedRelation/expectedGate/reviewStatus/origin.

- [ ] 기존10개와 신규 관계/합성 세트를 별도 partition으로 만든다. 새로운 문자열·문장 순서를 포함한다.
- [ ] expectedRelation은 사람이 확인할 정답 초안으로 저장한다. `reviewStatus=draft`를
  단위 테스트의 mock 정답 주입과 실제 모델 평가 승인으로 혼동하지 않는다.
- [ ] 후보 위치가 target 문자열의 지정 occurrence와 일치하고, 동일 명칭에 서로 다른 관계를 부여한
  대조가 있는지 확인한다. 정답표를 실제 prompt에 붙이는 경로는 만들지 않는다.
- [ ] 실제 평가에 쓰기 전 사람이 사례별 정답을 검토하도록 산출물을 제시한다. 이번에는 그 평가를 실행하지 않는다.

## Task S2: 좁은 관계 계약과 서버의 모순 검증

**Consumes:** E1 `resolve_units` 결과, 기존 `proposed_field`, spec의 RelationAssessment.
**Produces:** `validate_relation(registry: dict, candidate_id: str, assessment: dict) -> dict`,
`gate_external_claim(registry: dict, candidate_id: str, proposed_field: str,
assessment: dict | None) -> dict`.

출력은 gate(`allow_external_claim/reject_external_claim/needs_confirmation/not_applicable`),
reasonCode, 원형 assessment/근거 참조다. 사용자 확정 필드는 없다.

- [ ] S01–S06/S09/S13의 정상·오류 fixed assertion 테스트를 먼저 작성한다.
  같은 이름의 platform assertion은 reject_external_claim, 실제 서비스 assertion은 allow_external_claim.
  protocol+provider 문장은 protocol 후보와 provider 후보가 서로 다른 결과여야 한다.
- [ ] E1 단위 ID를 쓰는 reference corruption 테스트도 작성한다. 잘못된 sourceDigest, objectUnitIds가
  다른 occurrence를 가리킴, 비어 있는 predicate/subject 근거는 allow 결과가 나와서는 안 된다.
- [ ] `rtk proxy <venv-python> -m unittest discover -s tests -p test_external_relation_contract.py -v`로 RED 확인.
- [ ] 검증기를 구현한다. 주어·술어·목적어 단위의 ID·범위·source identity와 선택 상한을 검증한다.
  subject/predicate/object의 합집합을 support로 정의하고8단위·4000자 이하로 제한한다.
  counterUnitIds는 별도로8단위·4000자 이하를 적용한다. 초과/불완전 문맥은 보류다.
  거절·계획·과거·다른 프로젝트·상충에 대한 gate 표는 spec 그대로 적용한다.
- [ ] `proposed_field != external_integrations`는 not_applicable로 두고 기존 정상 field를 보존한다.
  외부 주장 경로는 gate 안에서 validate_relation을 호출해 참조 검증을 생략할 수 없게 한다.
  external_integrations인데 assessment가 없거나 unclear이면 보류하며 원문 후보를 지우지 않는다.
  supported_platform/uses_protocol가 명확하면 외부 주장만 거절하고 기능을 새로 합성하지 않는다.
- [ ] S07–S12/S14로 qualifier·상충·다른 프로젝트·불명확·다른 정상 필드 보호를 검증한다.
  실제 서비스 positive는 allow, 애매한 경우는 보류, 명백한 scope 밖/거절은 reject여야 한다.
- [ ] GREEN 확인 후 커밋한다. relation_prompt.md에는 구체 이름이나 정답표 없이 관계 정의,
  전체 문서·상충 확인, 주어/술어/목적어 근거 참조만 적는다. HTTP 호출 기능은 추가하지 않는다.

## Task S3: 정답 대조와 안전 한계가 드러나는 오프라인 보고

**Consumes:** 과거 A/B 원응답/정규화 결과, E2 audit, 수동 작성 mock RelationAssessment.
**Produces:** `build_offline_report(saved_records: list[dict], evidence_audits: list[dict],
relation_fixtures: list[dict], gold: list[dict]) -> dict`.

보고서는 `saved_baseline`, `binding_audit`, `mock_contract_results`, `unmeasured_live_quality`로 구분한다.
원모델 제안·서버 판정·최종 Profile을 따로 두고 사람 확정은 미측정이다.

- [ ] 기존 승인 gold 기준 A4/4/24, B3/2/37(오확정/정상누락/전체보류)을 재현하는 테스트 작성.
- [ ] S14에서 플랫폼 문장을 consumes_service로 잘못 assertion하되 ID와 위치는 모두 유효하게 만든다.
  규칙상 통과할 수 있음을 기록하고, **정답 채점기는 오확정1로 반드시 집계**해야 한다.
  이 테스트를 관계 모델의 성공으로 표시하면 실패다.
- [ ] 전부 보류 mock은 정상 positive의 누락/보류 증가로 실패, 전부 거절 mock은 실제 외부 서비스
  누락으로 실패한다. 정상례를 없애서 오확정만 줄이는 방법을 통과시키지 않는다.
- [ ] `rtk proxy <venv-python> -m unittest discover -s tests -p test_evidence_relation_replay.py -v`로 RED→GREEN.
- [ ] 입력/source/원응답 해시, 후보 유실0, 실제 호출0을 보고한다.
  새 모델 정확도/호출수/처리시간은 **미측정(null)**으로 기록한다. mock의0을 실제값으로 복사하지 않는다.
- [ ] 당시 전체 로컬 회귀를 실행하고 결과를 커밋한 뒤 중단한다. 실제 모델 평가/배포로 이어가지 않는다.

## 검토 초점 및 후속 판단

- 동일 명칭이 플랫폼과 API 서비스로 쓰임: S01/S02. 이름 규칙에 의존하면 실패.
- 한 문장의 provider/protocol 결합과 순서 반전: S03/S04/S06. 관계 객체를 뒤바꾸면 실패.
- 올바른 명칭이 다른 프로젝트/과거에만 등장: S07/S08. 전역 이름 일치로 확정 금지.
- relation enum과 인용이 모두 형식상 맞아도 의미는 틀릴 수 있음: S14. 미측정·오확정 정직하게 노출.
- 정상 기술/프로젝트명 및 서비스가 보류로 몰림: S10/S11와 기존 정상6개. 별도 누락 지표로 방지.

후속 로컬 작업 예산 제안3시간, 테스트 명령당5분, 원인 수정 뒤에만 재실행. 모델/API 예산0.
이후 실제 검증은 입력·사람 검토 gold·모델·무료 범위·호출수·시간 상한을 새로 승인받은 경우에만 별도 계획한다.
위 local mock 성공만으로 이 관계 구조가 기존 A/B보다 정확하다고 결론 내리지 않는다.
