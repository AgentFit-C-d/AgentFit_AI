# 원문 위치 기반 근거와 외부 연동 관계 검증 설계안

상태: 사용자 요청에 따른 **분석·계획 초안**, 구현/모델 호출/서비스 적용 승인으로 간주하지 않는다.
범위: [분석](analysis.md), [근거 계획](evidence-plan.md), [관계 계획](relation-plan.md),
[회귀 사례](regression-cases.md). 기존 SDD 관례에 따라 specs 아래에 보존한다.

## 목적과 제약

이미 확보한 후보의 위치를 안정적으로 사용하고, 플랫폼·프로토콜·서비스의 관계를 구분한다.
근거 문자가 존재한다는 이유로 의미상 확정하지 않는다. 정상 정보의 누락과 불필요한 확인 요청도 함께 보호한다.

- 이번 작업은 문서만 작성한다. 새 모델/API 호출0, B 반복·서비스·Spring·배포 변경0, 큰 goal paused.
- 기존18개 원응답, 원문/후보68개/rejected24개, 승인10개 정답과 기존 점수는 불변.
- 이름·브랜드·프로젝트·문서/후보 ID·URL별 예외나 정답 주입을 제품 규칙에 사용하지 않는다.
- 불확실한 후보는 원문 위치와 문맥을 보존하여 확인 필요로 남긴다.
- 모델 판정과 사용자 확정을 분리한다. 이 설계에는 사용자 승인 플래그를 쓰는 경로가 없다.
- 아래 구현은 이후 승인 시 **서비스 밖 로컬 실험**부터 진행하는 제안이다. 실제 호출은 별도 결정 사항.

## 검토한 대안

| 방식 | 장점 | 문제 / 결정 |
| --- | --- | --- |
| 모델에게 인용문 재생성·수정 요청 | 기존 응답 계약 유지 | 반복 위치/줄바꿈 오류 및 호출 증가. 이번 제한에서 실행하지 않음 |
| 기존 후보 위치와 서버 문맥 단위 참조 | 원문 복사·등장 순서 계산을 서버가 담당 | 위치와 의미를 혼동하지 않도록 별도 상태가 필요. 권고안 |
| 전 문서 개체 그래프·이름 사전 도입 | 넓은 관계 표현 | 이번 두 원인보다 범위가 크며 명칭 의존 위험. 보류 |

## A. 원문 위치 기반 근거

### 서버가 책임질 정보

- `sourceDigest`: 변경되지 않은 원문 UTF-8 SHA256.
- `candidateId`, `mentionSpan=[start,end)`, `value=document[start:end]`: 기존 후보에서 가져온다.
  정규화/재검색/첫 일치 치환을 하지 않는다. 단위는 Unicode code point다.
- `contextUnitIds`: 서버가 만든 **물리적 줄의 범위** 참조. 문장부호로 자르지 않아 약어·버전·URL을 보존한다.
  줄바꿈도 원래 문자 범위에 포함한다. 후보가 여러 줄에 걸치면 겹치는 모든 줄을 순서대로 연결한다.
- 각 단위는 `unitId,start,end,text,kind`를 가진다. kind는 line/heading 중 결정적으로 구분 가능한 구조만 표시한다.
  목록·표의 인접 줄/헤더는 별도 단위로 포함할 수 있으나 서버가 의미를 합성하지 않는다.
- 전체 원문과 기존 앞뒤240자 문맥은 유지한다. 원격 부정·개정·대상 프로젝트 정보는 전 문서 단위에서 선택한다.

### 이후 내부 응답의 제안

모델은 새로운 인용 문자열/등장 순서를 복사하는 대신 `candidateId`, `supportUnitIds`,
`counterUnitIds`를 참조하도록 설계한다. 인용 표시용 문자열과 위치는 서버가 원문에서 계산한다.
후보의 단어만 자동 인용한 것을 의미상 support로 취급하지 않는다.

- support에는 해당 후보를 포함하는 줄 단위가 필요하다. heading 단독은 support 불충분이다.
- 동일 sourceDigest의 유효 단위만 허용한다. 중복·존재하지 않는 ID·다른 문서 단위는 계약 오류다.
- 모든 줄을 전송해 빠진 구역이 없게 한다. 초기 로컬 계약 상한은 원문24000 code points,
  단위1000개, support/counter 선택 각각 최대8개, 한 선택 집합의 합계4000 code points다.
  초과 문맥은 잘라서 확정하지 않고 `context_incomplete`로 보류한다. 과거 실험 수치에는 적용하지 않는다.
- 반대 근거가 없다는 모델 출력을 서버가 의미 검증 완료로 해석하지 않는다.
- 이전 quote/occurrence는 원형 그대로 남긴다. 정확한 원문 위치에 매핑 가능한 경우에만 sidecar 참조를 추가하고,
  실패 시 `legacy_quote_unresolved`를 기록한다. 유사 문자열 자동 매칭·HTML unescape·줄바꿈 접기는 금지한다.

### 확정과 분리

근거 어댑터의 출력은 `mentionLocated`, `contextAvailable`, `legacyCitationStatus`다.
field/status/decision을 수정하지 않는다. 레거시 confirmed와 새 위치를 결합해 재확정하지 않는다.
실험의 새 판정이 필요하다면 선택 문맥에 대한 의미 판단을 별도로 받아야 한다.
로컬 고정 응답은 이 경로의 계약 검증에만 쓰고 실제 모델 개선으로 보고하지 않는다.

## B. 관계를 이용한 의미 판단

외부 연동 주장에 한정하여 **누가, 무엇을 위해/어떻게, 어떤 대상을 이용하는가**를 기록한다.
모든10개 필드에 또 다른 의미 역할 enum을 강제하지 않는다. 올바른 backend/frontend/project_name을
외부 제공자 역할 분류와 묶어 보류시키지 않는 것이 회귀 조건이다.

| 관계 | 객체의 의미 | 외부 연동 판정 |
| --- | --- | --- |
| supported_platform | 앱/확장이 실행되거나 호환되는 브라우저·OS·클라이언트 | 그 이름만으로 외부 서비스 확정 불가 |
| uses_protocol | 인증/통신/파일 교환의 규약·표준 | 규약 자체는 구체적 제공자가 아님 |
| consumes_service | 대상 제품이 명명된 외부 제공자의 인증·결제·보관·알림 등을 실제 사용/요구 | 대상·시점·채택·부정·상충 근거까지 충족하면 연동 제안 가능 |
| other | 내부 라이브러리·개발 도구·설명 등 위 관계가 아닌 것으로 명확함 | 현재 외부 연동 주장만 거절; 다른 필드의 정상 사실은 별도 유지 |
| unclear | 객체가 플랫폼인지 제공자인지, 또는 관계의 대상이 불명확함 | 후보/문맥 보존, 확인 필요 |

하나의 브랜드가 문서마다 플랫폼 또는 API 서비스일 수 있다. 같은 문서에서도 다른 occurrence이면 독립 판정한다.
`supports`나 `uses` 같은 동사, 대문자, URL 존재만으로 관계를 결정하지 않는다.
`제품 → 제공자의 서비스 호출 → 제공자`, `제품 → 실행/호환 → 플랫폼`,
`제품 → 규약 준수 → 프로토콜`의 방향을 해당 문장의 주어·술어·목적어 문맥에서 판단한다.

### 내부 기록 제안

`RelationAssessment`:
- candidateId, sourceDigest
- relation: 위5개 enum
- subject: target_project / other_project / unclear
- subjectUnitIds, predicateUnitIds, objectUnitIds: 같은 원문의 근거 참조
- assertion: current_adopted / proposed / negated / historical / unclear
- counterUnitIds, conflictState: none_found / unresolved / resolved_in_source

subject/predicate/object 단위 합집합이 support이며8개·4000자 이하, counter 집합도8개·4000자 이하다.

objectUnitIds는 해당 후보 위치를 포함해야 한다. 제품명이 생략된 목록은 제목/소개 문맥을 subjectUnitIds로 연결한다.
명시적 귀속 없이 다른 프로젝트 소개에서 주어를 가져오지 않는다. 기존 field 제안과 이 관계를 별도로 보존한다.
관계가 외부 연동 주장을 반박해도 원문에 없는 '브라우저 확장 기능' 후보를 새로 만들지 않는다.

서버 결과는 `allow_external_claim / reject_external_claim / needs_confirmation / not_applicable`이다.
reject는 해당 external_integrations 주장만 반박하는 의미다. 다른 올바른 field/기능이나 원문 후보 삭제가 아니다.
불명확·근거 부족·미해결 상충은 needs_confirmation. current_adopted는 문서상 모델 제안이며 사용자 확정이 아니다.
같은 시점·대상에 관한 명시적 거절은 reject, 검토/계획은 보류한다. 명시적 개정이 있으면 최신 결정 단위를 함께 보존한다.

gate 순서는 다음과 같다. 외부 연동 외 field에는 not_applicable을 반환한다.
외부 주장인데 assessment가 없으면 보류한다. 존재하면 내부에서 참조/스키마를 검증한다.
손상된 계약은 오류로 보존하고 허용 결과를 만들지 않는다. 불완전 문맥·unclear·미해결 상충은 보류한다.
other_project 또는 historical/negated는 해당 현재 외부 주장을 거절한다. proposed는 보류한다.
나머지 중 supported_platform/uses_protocol/other는 거절하고,
target_project + current_adopted + consumes_service이며 유효 근거/해결된 상충 조건을 충족할 때만 허용한다.
이 순서는 신규 관계 assertion의 로컬 일관성 규칙이며 원문을 이해하는 결정적 자연어 규칙이 아니다.

### 한계

서버는 `supported_platform`와 external_integrations의 모순을 검증할 수 있다.
하지만 모델이 플랫폼을 `consumes_service`로 일관되게 잘못 출력하면 참조 위치 검증만으로 적발할 수 없다.
관계 tuple은 관측과 판단 기준을 분명하게 하는 설계이며 의미 정확성의 증명이 아니다.
이 한계는 잘못된 mock 관계를 채점기가 오확정으로 세는 회귀로 남기고, 이후 실제 모델 검증 없이는 채택하지 않는다.

## 평가 분리와 중단 기준

1. 위치/문맥 연결의 결정적 로컬 검사: 기존68개 전부 보존, source identity/범위 정확, 기존 decision 변경0.
2. 주 승인 gold10개의 보관값 재현: A 오확정4·누락4·보류24, B 오확정3·누락2·보류37과 동일해야 한다.
3. 새 관계 정답/새 문맥은 [regression-cases.md](regression-cases.md)의 **사람 검토 전 초안**.
   기존10개에 섞거나 성공률을 계산하지 않는다.
4. 정상 외부 서비스, 정상 프로젝트명·frontend/backend, 실제 기능을 보호한다.
   전부 보류/전부 외부 연동 거절은 정상 대조 검사에서 실패해야 한다.
5. 위치 개선만 / 관계 개선만 / 함께 적용의 향후 검증을 분리한다. 모델 출력이 없는 조합은 미측정이다.
6. 오류 유형·서버 오확정·정상 누락·보류(전체/정상)·관계 불명확·원문 유실·호출수·시간을 따로 보고한다.
7. 이번에는 설계/테스트 계획 전달 후 종료한다. 실사용 판정, B 반복, 실제 모델 호출 예산은 승인하지 않는다.
