# AgentFit 역할별 Agent.md 배포 안내

각 팀원에게 담당 역할의 `Agent.md`를 전달한다. 각 파일에 제품 정의, 공통 요구사항, MVP 순서, 승인 절차와 역할별 작업·검증·인계 기준이 들어 있다.
개인 PC 경로·설치 상태·과거 대화 없이 읽을 수 있도록 구성했다.

모든 팀원에게 [기획서](../project-proposal.md), [공통 PRD](../PRD.md), [검증 실행 계획](../validation-plan.md), [본인 파트 PRD](../team-prds/README.md)와 역할별 `Agent.md`를 함께 전달한다.
[API 명세](../api/README.md)에서 첫 Feature의 요청·응답·오류와 후속 설계 초안을 확인한다.
PRD는 무엇을 만들고 어떤 기준으로 완료할지, 역할별 Agent.md는 담당 범위와 작업 방법을 설명한다. 검증 실행 계획은 실험 표본·절차·판정·담당과 실제 결과를 관리한다.
환경 확인 수준, 추가 도구 불필요 결과, 권한 통제 범위, Catalog 조합, 적용 안내와 보완 평가 기준은 다섯 역할 문서에도 공통으로 포함한다.

## 역할 선택

| 팀원 | 배포할 파일 | 주 담당 |
| --- | --- | --- |
| Full Stack A | [Agent.md](full-stack-a/Agent.md) | 서버·인증·DB·프로젝트·AI 서비스 통합·배포 |
| Full Stack B | [Agent.md](full-stack-b/Agent.md) | Tool Catalog·호환성·추천 Backend·Permission·Config |
| AI Developer | [Agent.md](ai-developer/Agent.md) | 문서 추출·Profile·근거 검증·Capability·품질 평가 |
| Frontend Developer | [Agent.md](frontend-developer/Agent.md) | 화면·상태·폼·API 연결·Preview·다운로드 UX 구현 |
| Designer | [Agent.md](designer/Agent.md) | 사용자 여정·화면·문구·권한 UX·사용성 검증 |

## 바로 사용하는 방법

1. 기획서·공통 PRD·검증 실행 계획·본인 파트 PRD와 Agent.md를 AI 작업 대화에 첨부하거나 읽을 파일로 지정한다.
2. 같은 팀 저장소와 담당 Feature/Task를 알려준다. 이미 있는 Spec·Plan·Tasks·계약을 먼저 사용한다.
3. 아래 시작 요청을 함께 전달한다.
4. 제시된 담당 범위·계약 영향·검증 계획을 확인하고 구현 시작 여부를 결정한다.

```text
첨부한 공통 PRD를 전체 제품 요구로, 내 파트 PRD를 담당 요구와 수용 기준으로 읽어줘.
Agent.md는 내 역할의 작업 지침으로 사용해줘.
검증 실행 계획에서 내가 담당할 평가와 아직 측정하지 않은 가정을 확인해줘.
먼저 팀 저장소의 기존 코드, Spec Kit 문서, API·데이터 계약과 담당 작업을 확인해줘.
내 역할에 필요한 첫 작업, 수정할 파일, 다른 역할에게 필요한 산출물,
검증 방법과 아직 결정되지 않은 사항을 정리해줘.
애플리케이션 구현이나 패키지 설치는 내 승인을 받은 뒤 시작해.
디자인·문서 요청은 요청한 산출물 범위 안에서 진행해.
```

별도 도구의 자동 파일 탐색에 의존하지 않고 해당 파일을 명시적으로 전달해서 사용한다.
팀원이 파일 하나만 받았어도 제품과 역할을 이해하고 작업안을 만들 수 있다. 실제 구현에는 같은 기준 저장소와 최신 명세가 필요하다.
문서가 없는 경우 다섯 명이 각각 새로운 기준을 만들지 말고 공통 Feature 명세를 팀에서 먼저 정한다.

## 겹치는 작업의 기본 분담

아래는 기본 협업안이며 실제 배정은 해당 Feature의 Tasks에 기록한다.

| 공통 산출물 | 작성·통합 | 함께 확인할 역할 |
| --- | --- | --- |
| 프로젝트·분석 API, DB·migration, 공통 서버 환경 | Full Stack A | AI·Frontend·해당 모듈 담당 |
| Profile 필드 의미·근거·미정 | AI가 제안, A가 공통 schema·저장/API에 통합 | Frontend·Designer |
| 텍스트 추출·AI 분석 | AI | A가 실행·중단·상태·저장과 연결 |
| Catalog·호환성·추천 판정 | Full Stack B | AI가 Capability·설명 근거 연결 |
| 권한 정책·설정 산출물·Preview 데이터 | Full Stack B | A가 보안·저장, Frontend·Designer가 사용자 흐름 확인 |
| 제품 화면과 API 연결 | Frontend | Designer·A·B·AI 중 관련 담당 |
| 화면·상태·문구·사용성 평가 | Designer | Frontend와 관련 Backend·AI 담당 |
| 공통 Spec·Plan·Tasks 변경 | 팀이 지정한 해당 Feature 통합 담당 | 영향받는 역할 |

계약을 바꿀 때는 필드·타입·상태·오류·보관 정책의 변경 이유와 소비하는 역할의 영향을 함께 기록한다.
역할별 코드에 같은 계약을 복제하지 말고 합의된 공통 schema와 API 계약을 사용한다.

## 개발 순서

1. 프로젝트·문서 분석·확인 저장 흐름을 먼저 완성한다. A·AI·Frontend·Designer가 주로 연결하고 B는 배정된 검토·검증과 후속 조사로 기여한다.
2. 실제 첫 흐름이 동작하면 역할·환경 → Capability → Catalog·호환성 → 추천으로 확장한다.
3. 이후 권한 → Config → Preview → 최종 승인 → 다운로드와 적용·인증·사용 확인 안내를 완성한다.

첫 단계가 끝나기 전 후속 서비스 구현을 선행하지 않는다. 준비·조사·계약 초안과 구현을 구분한다.
과거 행동 인터뷰·환경/권한 반례·Catalog 자료 검토는 먼저 할 수 있다. 실제 실행 코드·설치가 필요한 검증은 승인된 구현 범위에서 수행한다.
한 역할의 완료와 전체 Feature의 통합 완료를 따로 기록한다.

## 배포 문서 유지

- 공통 원칙과 확정 요구사항은 각 파일에 포함되어 있어 다른 역할의 파일을 추가로 읽을 필요가 없다.
- 공통 요구사항이 변경되면 팀의 Spec Kit 문서를 먼저 갱신하고 다섯 역할의 같은 내용도 함께 수정한다.
- 실제 패키지 버전·설치 호환성·명령·운영 준비 조건은 팀 Plan·lockfile·실행 안내에서 관리한다. 이 문서 자체는 설치 검증 결과가 아니다.
- 개인 진행률·설치 오류 이력은 Feature 검증 기록에서 관리한다.
