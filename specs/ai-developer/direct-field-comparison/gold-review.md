# 비교 전 정답 기준 검토본

**2026-10-01 사용자 승인 / human_reviewed=true / A/B한 쌍의 사전 기준.**

근거는 저장된 [linkding 원문](E:/AgentFit/output/semantic-role-service-path-v1/linkding.md)이다.
범위는 0부터 시작하는 Unicode code point의 `[start,end)`이며 후보 식별자는 평가용 주소다.
후보 ID·프로젝트명·브라우저명에 따른 정답 규칙을 제품 코드/모델 prompt에 넣지 않는다.

## 공통 분류 기준

- 프로젝트명: 문장이 대상 제품의 이름임을 명시한다.
- frontend/backend: 실제 제품 구현에 쓰는 언어·프레임워크다. 개발 문서에 있다는 이유로
  전부 제외하지 않는다. 테스트·포맷터·패키지 관리자는 실제 제품 기술과 구분한다.
- project_type: 제품의 제공 형태다. 단순한 이름과 설치/사용 동작은 구분한다.
- features: 원문이 명시한 제품/사용자 동작이다. 기술명·브라우저명·홍보 수식만으로 생성하지 않는다.
- external_integrations: 제품이 기능을 위해 연동하는 외부 서비스 제공자다.
  지원하는 브라우저, 프로토콜, 라이브러리, 문서 링크를 곧바로 외부 서비스로 보지 않는다.
- `confirmed`: 현재 대상 제품의 명시된 사실이라는 **모델 제안**이다. 사용자 확정 아님.
- `tentative / needs_confirmation`: 의미 또는 근거가 부족하면 원문과 후보를 보존한다.
- `other / irrelevant / excluded`: 이 occurrence 자체가 Profile의 해당 종류 사실이 아니다.
  후보 기록은 유지하며 삭제로 처리하지 않는다.

## 주 평가 정답 초안 — 10개

| ID / 후보 | 원문 문맥·위치 | 기대 필드 / 판정 | 피해야 할 판단 |
| --- | --- | --- | --- |
| G01 C013 Firefox | L28 `Extensions for [Firefox] ... and [Chrome]`, 978:985 | other / irrelevant → excluded | 브라우저 이름을 external_integrations/confirmed 또는 단독 features로 제안 |
| G02 C015 Chrome | 같은 L28, 1054:1060 | other / irrelevant → excluded | G01과 같음. 확장 기능 지원이라는 관계와 브라우저 이름을 구분 |
| G03 C001 linkding | L11 `linkding is a bookmark manager that you can host yourself.`, 180:188 | project_name / confirmed → supported | 이름을 product operation으로 분류해 보류하거나 기능으로 이동 |
| G04 C032 Django | L61 `The application is built using the Django web framework.`, 2625:2631 | backend / confirmed → supported | 문서 링크/외부 서비스/단순 개발 도구로 취급해 누락 |
| G05 C062 JavaScript | L124 `used for compiling JavaScript components like tag auto-completion`, 뒤에 `make frontend`, 4363:4373 | frontend / confirmed → supported | 개발 절차 문단이라는 이유만으로 제품 프론트엔드 언어를 제외 |
| G06 C012 Progressive Web App (PWA) | L27 `Installable as a Progressive Web App (PWA)`, 934:959 | project_type / confirmed → supported | 서비스 형태를 features로만 이동해 project_type 누락 |
| G07 C010 Internet Archive | L25 `Automatically archive websites ... on Internet Archive`, 844:860 | external_integrations / confirmed → supported | 실제 명시된 연동까지 전부 보류/제외 |
| G08 C005 Organize bookmarks with tags | L21 같은 문구, 565:593 | features / confirmed → supported | 실제 제품 동작까지 설명 문구로 제외 |
| G09 C004 Clean UI optimized for readability | L20 같은 문구, 528:562 | other / irrelevant → excluded | 품질·홍보 설명을 독립 제품 동작으로 확정 |
| G10 C048 pytest | L94 `Run all tests with pytest:`, 3555:3561 | other / irrelevant → excluded | 테스트 도구를 backend 또는 외부 연동으로 확정 |

양성6개(G03–G08), 음성4개(G01/G02/G09/G10). 사용자가 제시된 기준으로 진행을 승인했다.
평가기는 ID를 원문 위치와 함께 검증하며, model prompt에 이 표나 기대값을 보내지 않는다.

## 먼저 확인할 경계

1. **PWA:** 이 비교의 단일 후보 우선 필드는 project_type으로 제안한다.
   별도 원문 동작인 ‘앱으로 설치 가능’을 features로도 표현할지는 별도 기준이다.
   이번 후보는 PWA 명사구뿐이므로 임의로 ‘설치 기능’ 후보를 추가하지 않는다.
   이전 평가는 PWA의 features 출력을 추가 오탐으로 세지 않았다. 이번 표를 승인하면
   필드 오류로 셀 수 있으므로 과거 점수와 절대값을 직접 비교하지 않고 A/B에 같은 기준을 쓴다.
2. **JavaScript:** G05는 명시적인 프론트엔드 컴포넌트 문장이다. C053의 포맷터 문장만을
   동일 강도의 근거로 삼지는 않는다. C053 단독 판정은 별도 사람 검토 대상으로 둔다.
3. **Firefox/Chrome:** 이름 자체는 지원 플랫폼이고, ‘브라우저 확장 지원’은 다른 기능 사실이다.
   후자는 저장 후보68개에 없으므로 이번 분류 실험의 정상 누락 분모에 넣지 않는다.
4. **반복된 이름:** URL의 linkding과 소개 문장의 C001, Django docs와 구현 설명 C032는
   같은 철자여도 같은 occurrence 정답으로 일괄 처리하지 않는다.

## 주 점수 밖 항목

- 셀프호스팅·Docker·DevContainers가 실제 채택 배포인지 여부, Python/Node.js의 실행 역할,
  Django templates, domain과 bookmark manager, 나머지 이름 반복 occurrence.
- 전체68개 중 주 평가10개 외58개는 입력/출력/보류 상태를 전부 보존하고 사람 검토로 분리한다.
  이들의 출력은 무조건 정답으로 인정하지 않는다. 양쪽 결과를 가린 상태로 검토한 뒤
  어느 한쪽에서 새로운 명백한 오확정이 발견되면 채택을 보류한다.
- 평가 후 정답을 바꾸려면 새 버전을 만들고 양쪽을 같은 기준으로 재채점한다.
  한쪽 결과만 유리해지도록 분모·허용 필드·별칭을 수정하지 않는다.

## 검토 완료 기록

- 검토자/검토일: 사용자 / 2026-10-01
- 승인 근거: “제시한 정답 기준으로 진행하되”라는 이번 직접 지시.
- G01–G10, PWA 단일 필드 및 점수 밖58개 처리: 제시된 기준 그대로 승인.
- 실제 비교 범위: 무료 NVIDIA 최대18회, A/B한 쌍만. 추가 반복 미승인.
