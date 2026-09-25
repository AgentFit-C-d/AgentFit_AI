# AgentFit 팀 배포 문서 안내

> 기준일: 2026-09-08 · 기획 설명과 파트별 요구사항 전달용

## 1. 팀원에게 전달할 문서

모든 팀원에게 기획서·공통 PRD·API 명세·검증 실행 계획을 전달하고, 각자 담당 파트의 PRD와 Agent.md를 추가한다.

| 문서 | 쓰임 |
| --- | --- |
| [프로젝트 기획서](../project-proposal.md) | 팀 회의에서 문제·목표·사용 흐름·범위·분담을 설명 |
| [공통 PRD](../PRD.md) | 전체 제품 요구 PRD-01–41과 공통 정책·성공 기준 확인 |
| 아래 파트별 PRD | 각자 제공할 제품 결과·요구사항·수용 기준·인계 확인 |
| 각 파트의 Agent.md | AI 작업의 진행 방식·승인·경계·보고 기준으로 사용 |
| [API 명세와 OpenAPI](../api/README.md) | 요청·응답·오류·버전·상태를 화면과 서버가 함께 사용 |
| [검증 실행 계획](../validation-plan.md) | 사전 정답·실험·표본·담당·판정·실제 결과 관리 |

## 2. 파트별 전달 파일

| 파트 | PRD | AI 작업 지침 | 주요 결과 |
| --- | --- | --- | --- |
| Full Stack A | [PRD](full-stack-a/PRD.md) | [Agent.md](../team-agents/full-stack-a/Agent.md) | 인증·프로젝트·API·저장·복구·삭제·서버 통합 |
| Full Stack B | [PRD](full-stack-b/PRD.md) | [Agent.md](../team-agents/full-stack-b/Agent.md) | Catalog·호환성·추천·권한·Config·상태 근거 |
| AI Developer | [PRD](ai-developer/PRD.md) | [Agent.md](../team-agents/ai-developer/Agent.md) | 추출·Profile·문맥 의미·Capability·설명·평가 |
| Frontend Developer | [PRD](frontend-developer/PRD.md) | [Agent.md](../team-agents/frontend-developer/Agent.md) | 화면·입력·편집·상태·권한/Preview·다운로드 안내 |
| Designer | [PRD](designer/PRD.md) | [Agent.md](../team-agents/designer/Agent.md) | 사용자 흐름·화면·문구·접근성·실제 사용성 평가 |

각 PRD에는 제품 맥락과 핵심 공통 제약을 포함했다. 파일 하나로 담당 범위는 이해할 수 있지만 실제 개발에는 공통 PRD와 같은 팀 저장소의 최신 기술 명세가 필요하다.

## 3. 먼저 합의할 인계 경계

2026-09-25 사용자 결정에 따라 초기 설정 대상 Client는 Codex이고, 문서 분석의 1차 평가 모델은 Solar Pro 4다. 팀 합의 전 검토 자료는 [AI 인계 계약 초안](../../specs/ai-developer/01-profile-contract/handoff-draft.md)과 [Provider 평가 절차](../../specs/ai-developer/provider-evaluation.md)에 둔다. 실제 Provider 채택과 Codex 설정 지원 조합은 검증 후 확정한다.

| 산출물 | 작성·통합 책임 | 함께 확인 |
| --- | --- | --- |
| 프로젝트·분석·Profile API / 공통 DB | A 통합 | AI·Frontend·관련 모듈 담당 |
| Profile 필드 의미·미정·근거 | AI 제안, A 공통 계약 통합 | Frontend·Designer |
| 텍스트 추출·Provider 결과 | AI | A가 입력 제한·Worker 종료·상태·저장 연결 |
| Catalog·호환성·추천 판정 | B | AI의 Capability·설명, Frontend의 상태 처리 |
| 권한·Config·Preview 결과 | B | A의 공통 보안·저장, Frontend·Designer의 사용자 흐름 |
| 실제 화면·폼·API 연결 | Frontend | Designer·관련 A/B/AI |
| 화면·문구·사용성 평가 | Designer | Frontend와 관련 서버·AI 담당 |
| Feature Spec·Plan·Tasks 변경 | 팀 지정 통합 담당 | 영향을 받는 모든 파트 |

파트별 PRD의 Task 연결은 기본 분담안이다. 동일 Task에서 맡을 구현 파일·검토 범위를 확인하고 공통 파일의 최종 통합 담당을 한 곳으로 정한다.

## 4. 첫 작업과 진행 순서

1. **기획 공유:** 기획서의 설명용 사례로 입력부터 설정 안내까지 전체 흐름을 이해한다.
2. **계약 확인:** 첫 Feature의 Spec·Plan·Tasks·데이터 모델·HTTP 계약을 함께 확인한다.
3. **첫 산출물:** A는 공통 계약, AI는 필드 의미·사전 정답, Frontend는 화면 상태 대응표, Designer는 연결된 화면·문구, B는 보안·환경 반례와 후속 지원표 초안을 준비한다.
4. **구현 승인:** 대상 Task·파일·선행 산출물·계약 영향·검증 방법을 정리하고 해당 작업을 요청한 사용자의 승인을 받은 뒤 코드·설정·테스트 작성과 설치를 시작한다.
5. **첫 통합:** 로그인 → 개인 프로젝트 → 문서 분석 → 확인·수정·저장·재접속 → 실패 복구·삭제를 검증한다.
6. **후속 단계:** 첫 흐름 완료 후 역할·환경·추천, 그다음 권한·설정·다운로드·적용 안내를 구현한다.

인터뷰·공식 자료 조사·수동 반례·설계 준비는 병행할 수 있다. 코드·설치가 필요한 검증은 승인된 범위에서 수행한다. 실제 사용자 모집이나 외부 메시지 발송은 별도 요청에 따른다.

## 5. 팀원에게 보낼 소개 문구

> AgentFit은 기획서와 역할을 바탕으로 개발환경을 확인하고, 필요한 AI 구성과 설정·적용 방법을 안내하는 서비스입니다.
> 먼저 기획서로 전체 흐름을 보고, 공통 PRD와 본인 파트 PRD에서 담당 요구와 완료 기준을 확인해 주세요.
> 첫 구현은 프로젝트·문서 분석·수정·저장까지 연결합니다. 각 파트가 공통 계약을 맞춘 뒤 승인된 Tasks를 진행합니다.
> Agent.md는 AI와 작업할 때 함께 전달할 지침입니다. 문서에 적힌 평가 수치는 목표이며 실제 통과 결과가 아닙니다.

## 6. 문서 기준과 업데이트

- 기획서는 설명, 공통 PRD는 전체 요구, 파트 PRD는 책임과 수용 기준, Agent.md는 작업 지침이다.
- 실제 개발의 우선순위는 Constitution → Feature Spec·Clarification → Plan → Tasks → 코드다. 파트별 문서가 별도 Source of Truth를 만들지 않는다.
- 파트 ID(FSA·FSB·AI·FE·UX)는 공통 PRD 식별자에 연결되는 추적용 ID다. 현재 Feature의 FR·SC·T 식별자를 새로 정의한 것이 아니다.
- 공통 요구가 변경되면 공통 PRD·해당 Feature·영향받는 파트 PRD·Agent.md와 기획서 설명을 함께 정합화한다.
- 지원 도구·권한·OS/Client 버전·계약 필드의 상세 결정은 해당 Feature에서 실제 근거로 확정한다. 미검증 환경을 지원 완료로 표시하지 않는다.
- 패키지 버전·개인 경로·설치 이력·개인 진행률은 이 배포 PRD에 복제하지 않는다.
- 문서 간 일치, 애플리케이션 동작, 실제 사용자 가치 검증을 구분해 보고한다.
