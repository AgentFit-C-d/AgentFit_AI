# 고정 B 지침 · 새 합성 문맥 A/B 결과

## 결론

새 합성 문서2개에서 **역할 오류 10→0, 정상 후보 supported 3/9→9/9**로 개선 방향이 관측됐다. 실제 인증·SDK 데이터·SDK 인증의 정상 연동3개는 양쪽 모두 supported였다. 동일 이름의 호환 대상과 외부 제공자 역할도 B에서 구분됐다.

그러나 **상태 판단은 해결되지 않았다.** B의 `other/confirmed`는2건, 예시 프로젝트와 명시 부정에 대한 유효필드 `confirmed` 오류도2건이었다. 서버 통과 오답은1→0이지만, 모델 자체의 잘못된 confirmed는 없어지지 않았다. 이를 완전한 분류 개선이나 서비스 적용 준비 완료로 평가하지 않는다.

**실제 새 호출4/4 성공, 재시도0, 전체175.438초.** D1 A→B, D2 B→A 순서 그대로 실행했다. 추가 모델 호출·GLM·전체 추출·서비스 적용·Spring 저장·사용자 확정0. 큰 Goal paused 유지.

## 실행 전 고정과 사전 검증

- 기준 실행 코드: `914e97b144a39858eb6ab2b8407323494888d82b` / `feature/role-context-ab`.
- 모델 `deepseek-ai/deepseek-v4.1-flash`, endpoint `https://integrate.api.nvidia.com/v1/chat/completions`. 현재 사용자 승인이 지정한 앞서 확인된 무료 범위만 사용. 추가 계정/잔여량 확인 호출, 유료 전환·대체0.
- A는 현행 MENTION_ROLE_INSTRUCTION, B는 직전 실험 동결파일의 바이트 그대로. B SHA256 `f6c4265d4f459babee04e5ed010b9ac81525dcbe3c77ba784ebd54dbb0229523`.
- 양쪽 모델·다른 system 지침·schema·서버·8192출력토큰·temperature0·thinking=false·stream=true 동일. 이전 schema와도 후보 ID enum 외 동일함을 로컬 검사했다. 모델에는 문서 전체, 8후보 ID/원문 위치/값/앞뒤240자만 전송했다. 기대값·판정 해설 전송0.
- 사전 원문/기대값: [고정 평가 계획](./context-comparison-plan.md), [원문과 기대값 자료](../../../work/harness/role-context-ab/cases.json). 기존 AgentFit 40개 의미 골드는 수정하지 않았다. 이 자료는 실행 전 작성한 별도 합성 기준이며 실제문서 골드나 사람 독립 검증 자료가 아니다.
- 기존12+신규15 = **27개 로컬 테스트 통과**, skip/검증완화0. 네트워크 차단 상태에서 순서·4회상한·재시작차단·첫실패1~4번째·전역시간공유·만료전송차단·진행중자식종료·기밀문자열 저장차단·정답누출방지·서버/인용별도채점 검증.
- 독립 검토에서 양쪽 근거를 요구한 상충 채점이 support=[]을 허용하는 P2 발견. 실제 호출 전에 RED로 재현 후 유효support의 선택후보 포함까지 요구하도록 평가기만 수정했다. 빈 support/잘못된 occurrence/다른 후보 support 회귀 통과. 모델·B·기대기준·서버 변경0.
- 초기 RED, 수정 후 GREEN, 최종 로그 모두 보존. [최종 검증 로그](E:/AgentFit/output/role-context-ab-preflight-20261003T092738411584Z/role-context-ab.txt). 기존 Python의 `<prefix>` 경고는 있었으나 테스트는 모두 실행·통과했다. 설치나 환경 변경은 하지 않았다.
- 실행 전 SHA256 동결과 실행 후/오프라인 재검산 모두 일치. 미커밋 기존 사용자 작업도 freeze.json에 상태를 기록하고 보존했다. 실제 실행 파일은 code-snapshot에 보관했다.

## 자료와 집계 단위

| 문서 | 길이 | 후보 | 정상 긍정 | 범위 밖 | 명시 부정 | 미정/상충 |
|---|---:|---:|---:|---:|---:|---:|
| D1 LatticeDesk | 521 Unicode 문자 | 8 | 5 | 2 | 1 | 0 |
| D2 HarborLedger | 599 Unicode 문자 | 8 | 4 | 2 | 0 | 2 |

후보는 발생 위치 단위다. 같은 제공자도 인증·데이터·백업이라는 다른 관계를 별도 평가했다. 원문에 명시한 범위가 다르므로 서로 모순으로 만들지 않았다. 전체 Profile 출력이나 기존40개 의미의 보존율은 측정하지 않았다. 원문 위치는 Unicode 코드포인트의 `[start,end)`다.

## 문서별 비교

| 지표 | D1 A | D1 B | D2 A | D2 B | 합계 A→B |
|---|---:|---:|---:|---:|---:|
| mentionKind 역할 오류 | 5 | 0 | 5 | 0 | **10→0** |
| field 오류 | 0 | 0 | 1 | 0 | 1→0 |
| modelStatus 오류 | 2 | 3 | 1 | 1 | **3→4** |
| 정상 supported | 2/5 | 5/5 | 1/4 | 4/4 | **3/9→9/9** |
| 정상 보류 | 3 | 0 | 3 | 0 | 6→0 |
| 정상 제외 | 0 | 0 | 0 | 0 | 0→0 |
| 후보 응답 누락 | 0 | 0 | 0 | 0 | 0→0 |
| 유효field의 잘못된 confirmed | 0 | 2 | 1 | 0 | **1→2** |
| 서버 supported 통과 오답 | 0 | 0 | 1 | 0 | **1→0** |
| other/confirmed | 1 | 1 | 0 | 1 | **1→2** |
| 범위 밖 항목의 서버 제외 | 0/2 | 2/2 | 1/2 | 2/2 | 1/4→4/4 |
| field·역할·상태·요구축까지 맞은 올바른 제외 | 0/2 | 0/2 | 0/2 | 1/2 | **0/4→1/4** |
| 명시 부정의 올바른 negated+제외 | 0/1 | 0/1 | 해당없음 | 해당없음 | 0/1→0/1 |
| 미정/상충 raw 판단 및 필요한 상충 양쪽 근거 일치 | 해당없음 | 해당없음 | 2/2 | 2/2 | 2/2→2/2 |
| 미정/상충 실제 보류 | 해당없음 | 해당없음 | 1/2 | 1/2 | 1/2→1/2 |
| tentative/proposed인데 서버 제외 | 0 | 0 | 1 | 1 | 1→1 |
| 인용 결함 후보 | 0 | 0 | 0 | 0 | 0→0 |

`유효field confirmed 오류`와 `other/confirmed`는 별도 항목이다. 예시 이름의 scope=other나 부정의 polarity=negative를 모델이 보존했더라도 confirmed는 현재 대상의 긍정 사실이라는 상태 계약에 어긋나므로 원시 상태 오류로 집계했다. 서버가 그 축을 보고 제외한 것을 모델 정답으로 바꾸지 않았다.

정상9개에 대해 B는 전부 보류하지 않고9개 모두 supported였다. A의 정상정보는 응답 자체에서 사라지거나 제외된 것이 아니라6개가 역할 불일치로 보류된 것이다.

## 사례별 해석

### 대상 이름·제공 형태·도메인

D1 C000–C002와 D2 C000–C002 총6개는 A에서 `field`는 맞았지만 모두 `mentionKind=product_operation`이어서 보류됐다. B는 모두 `mentionKind=other`로 응답하고, 현재 대상의 긍정 사실 축과 confirmed를 유지해 supported가 됐다. 다른 제품명 예시2개까지 포함한 이름류 역할 오류는8→0이다. 지원 대상 이름2개도 external_service→other로 바뀌어 전체 역할 오류는10→0이다.

### 같은 이름의 서로 다른 관계: OrionID

| 후보/위치 | 원문 관계 | A | B |
|---|---|---|---|
| C004 `[176,183)` | 설정 파일이 지원하는 데스크톱 Client | other / external_service / confirmed → 보류 | other / other / confirmed → 제외 |
| C005 `[280,287)` | 실제 로그인 인증 제공자 | external_integrations / external_service / confirmed → supported | 동일, supported |
| C006 `[364,371)` | 공식 SDK로 기관 목록 데이터 제공 서비스를 호출 | external_integrations / external_service / confirmed → supported | 동일, supported |
| C007 `[438,445)` | 외부 백업 서비스와는 연동하지 않기로 결정 | external_integrations / external_service / irrelevant → 제외 | external_integrations / external_service / confirmed → 제외 |

정상 인증/SDK 데이터 연동은 B에서도 지원 대상으로 잘못 제외되지 않았다. 두 응답 모두 백업의 부정을 인증/데이터의 counterEvidence로 연결하지 않았다. 그러나 백업 부정의 기대 상태 `negated`는 A/B 모두 실패했다. B는 `polarity=negative`를 보존하면서 `confirmed`로 답했고 서버가 부정 축으로 차단했다. **역할 구별 개선과 부정 상태 실패가 동시에 관측됐다.**

호환 대상은 B에서 field/mentionKind는 기대와 일치하나 `modelStatus=confirmed`, `role=product_fact`여서 올바른 제외 정답으로 집계하지 않았다.

### 다른 제품 예시와 지원 Client

- D1 PebbleBoard C003: A는 project_name/product_operation/irrelevant, scope=other → 보류. B는 project_name/other/**confirmed**, scope=other → 제외. 역할은 개선됐지만 상태는 악화됐다.
- D2 PineQueue C003: A는 other/product_operation/irrelevant, scope=other/non_product → 제외. B는 other/other/irrelevant, scope=other → 제외. A는 결과적으로 제외했지만 역할이 틀려 엄격한 전체 조합 정답에는 포함하지 않았다. B는 고정 기준을 충족했다.
- D2 NimbusGate C004: A는 external_integrations/external_service/confirmed와 모든 긍정 축으로 **supported 오답**. B는 other/other/confirmed → 제외. 서버 통과 오답을 막았지만 `other/confirmed`와 product_fact 축의 잘못된 조합은 남았다.

### 정상 SDK 인증, 채택 미정, 해결되지 않은 상충

- D2 RiverPass C005: 공식 SDK를 통한 실제 로그인 제공자. A/B 모두 external_integrations/external_service/confirmed → supported. 다른 제공자 이름의 상충을 전이하지 않았다.
- D2 RelayWave C006: A/B 모두 external_integrations/external_service/**tentative**, commitment=**proposed**, target/current → **excluded**. 모델의 채택 미정 판단은 맞았고 서버가 보류로 남기지 않는 기존 정책 문제다. 이번에 수정하지 않았다.
- D2 VaultMesh C007: A/B 모두 external_integrations/external_service/tentative, polarity=unclear/commitment=unclear → 보류. 양쪽 모두 아래 두 문장과 미해결 설명을 support로, 부정 문장을 counterEvidence로 선택했다.
  - 긍정: “결정 기록 가: 이번 릴리스의 로그인에 VaultMesh 인증 서비스를 제공자로 사용한다.”
  - 부정: “결정 기록 나: 이번 릴리스의 로그인에 VaultMesh 인증 서비스를 제공자로 사용하지 않는다.”
  - 동일 대상/릴리스/로그인 결정이며 우선순위도 해결되지 않았다는 마지막 문장도 선택했다.

이 두 미정 사례의 원시 판정은 A/B 차이가 없었다. 보류되는 후보1개와 서버가 제외하는 후보1개를 합쳐 모두 안전한 보류라고 보고하지 않는다.

## 후보별 전체 원시 결과와 근거

[32행 대조표: field·mentionKind·modelStatus·5개 의미 축·서버 판정](E:/AgentFit/output/role-context-ab-20261003-v1/candidate-results.md)

[원문 위치·support·counterEvidence·검증 결과를 포함한 TSV](E:/AgentFit/output/role-context-ab-20261003-v1/candidate-results.tsv)

32개 응답 행 모두 conflictsChecked=true, groundingValid=true였고 인용은 occurrence=0이었다. quote 부재0, occurrence 오류0, 선택 후보 미포함0. 인용이 맞다고 의미 상태도 맞는 것은 아니며 위 status 오류는 별도로 남는다. 인용 오류 감소 효과는 이번에는 관측되지 않았다(양쪽0).

## 시간과 제한

| 실제 순서 | 요청 | 시간 | 전송 timeout |
|---:|---|---:|---:|
|1|D1 A|33.722초|600초|
|2|D1 B|32.106초|600초|
|3|D2 B|45.862초|600초|
|4|D2 A|63.325초|600초|

전체175.438초. 모델별/실험별 재시도0, 대체0, 실패0. 총1220초·종료여유20초와 요청당600초 모두 준수했다. 전역 남은 시간이 모든 요청에서600초 이상이라 이번 실실행에서는 timeout 축소가 필요하지 않았다. 줄어든 예산과 만료 중단 동작은 별도 오프라인 모의시간/자식프로세스 테스트로 확인했다. 문서1/2 모두 A/B가 완성돼 부분 결과는 없다.

## 보존 자료

실행 폴더: [role-context-ab-20261003-v1](E:/AgentFit/output/role-context-ab-20261003-v1)

- [freeze.json](E:/AgentFit/output/role-context-ab-20261003-v1/freeze.json): Git커밋/dirty상태/실제파일·지침·요청·원문·후보·기대값 해시.
- [suite.json](E:/AgentFit/output/role-context-ab-20261003-v1/suite.json): 모델 입력과 별도 기대값. 기대값은 요청 messages에 포함하지 않았음.
- D1/D2 하위: document.txt, candidates.json, expected.json, A/B-role-instruction.txt, request/wire-request/response/assessment/metadata.json.
- [calls.json](E:/AgentFit/output/role-context-ab-20261003-v1/calls.json), [execution.json](E:/AgentFit/output/role-context-ab-20261003-v1/execution.json), code-snapshot, integrity-after.json.
- [verification.json](E:/AgentFit/output/role-context-ab-20261003-v1/verification.json): 외부 네트워크를 차단한 사후 재검산. 고정 채점=저장채점, 동결해시 동일, 호출순서·시간 준수. 이 검산의 추가 모델 호출0. audit-results.py는 실행 종료 뒤 작성한 오프라인 자료검사이며 실제 실행 코드를 변경하지 않았다.

| 파일 | SHA256 |
|---|---|
|D1 원문|434d30563015dda2faec409c2872637e4a29134c25ae4c672da1a7374837c94b|
|D1 후보|3ac1621b5ef48aa6b85ab48147f014a89ddd2e962c26de949906b2cafb3d5a69|
|D1 기대값|018114c33694568d14a8f722d0a79cf1528c78b275c04b80ff013f98f0ef49cc|
|D2 원문|fcfb51fd07858cc4675d38ab9b075744c021e097a327f627e0940cc1cb8a0fbb|
|D2 후보|542aee15b87e33141c33fb13ae0c67becca940a8385d69f18ef68bd53ea0c3f8|
|D2 기대값|41c50ae1b1727207314cdfcbb182f755018debd07630eba042c91fb53683e465|

## 해석의 한계 / 종료

짧고 관계가 명시적인 합성 문서2개의 각 한 쌍이다. 역할 구분의 효과가 원래 AgentFit 이름에만 국한된 결과는 아니라는 제한된 증거는 있지만, 자연스러운 실제 문서/긴 문서/다양한 도메인에 대한 일반화, 반복 재현성, 최종 Profile 정확도는 검증하지 않았다. 이름·형태·도메인6개와 정상 연동3개 결과는 후보 분류 경계의 결과다. 서비스 추출/검토/투영/사용자 확정/저장은 실행하지 않았다.

확인된 미해결: other/confirmed, 예시 대상의 confirmed, 부정의 negated 누락, tentative/proposed 서버 제외. B를 더 고치거나 서비스 상수에 적용하지 않는다. 실험 후 지침·기대값·채점·실행 코드는 변경하지 않았다. 결과 보고로 종료하며 큰 Goal을 재개하지 않는다.
