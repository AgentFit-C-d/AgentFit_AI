# Validation Record

## 2026-09-07 — 구현 전

- Constitution 1.0.0: 공식 resolve-template 성공, 10개 원칙, 미해결 placeholder 없음.
- Specify: 공식 create-new-feature 및 active feature pointer 생성.
- Clarify: 질문 5개/응답 5개 통합. 인증·한도·AI 복구·보관·GitHub 선택 확정.
- 기본 품질 체크리스트: 최초 11/16 → 최종 16/16. notes의 초기 지적은 최초 검토 이력이다.
- Custom Checklist: 공식 템플릿으로 20개 생성 후 별도 요구사항 검토 20/20.
- Checklist helper는 Plan 부재로 실패해 사용자 지정 순서에 맞춰 공식 resolver로 진행했다.
- Plan: 공식 setup-plan 성공, research/data-model/contracts/quickstart 작성, 설계 후 헌법 적합성 검토 통과.
- Tasks: 공식 setup-tasks 성공, T001–T046 생성. US1 6개 / US2 10개 / US3 5개 / US4 5개, 공통 작업 20개.
- Analyze: RequireSpec/RequireTasks/IncludeTasks 성공, 읽기 전용 정합성 분석 수행.
  기능 요구 24개 + 구현 가능한 성공 기준 9개 = 33개 모두 작업 연결(100%).
  SC-007의 5명 사용성 결과는 별도 사람 대상 검증 T044에 연결했다.
  치명적/높음 충돌 0, 중복 작업 문제 0, 미연결 필수 요구 0.
- 전후 extension hook: `.specify/extensions.yml`이 없어 실행 대상 없음.
- 위 결과는 문서/설계 검토이며 Application Build·Test·Acceptance 통과를 뜻하지 않는다.

## Implementation

구현 전 사용자 승인이 필요하다. 현재 구현은 승인 대기 상태이며 기존 T001–T046은 미완료다. 2026-09-25 사용자 결정으로 Codex 초기 지원과 Solar Pro 4의 1차 평가 방향을 문서에 반영했다. Provider 실제 호출·성능 측정·최종 채택은 미수행이며 새 T047도 미완료다.

2026-09-25 추가 결정: Solar 시험은 로컬에서 시작하고 배포 시 서버 `.env`에 키를 설정한다. 평가 호출 예산에 별도 상한은 없으며 호출 수·비용은 기록한다. 사용자는 Upstage API 키 발급을 확인했다. 이 세션의 로컬 키 설정 여부는 확인하지 않았고 실제 Solar 호출은 수행하지 않았다.

### 2026-09-07 — 승인 전 시작한 초기 설정 취소

- 사전 확인 없이 초기 설정 파일 12개를 생성하고 패키지 설치를 시도했다.
- 사용자의 "구현 전엔 물어봐" 지시에 따라 즉시 작업을 중단했다.
- 설치는 Better Auth 1.7.3의 optional peer Vitest 지원 범위(2–4)와 선택한 Vitest 5.0.0의 충돌로 실패했다. node_modules와 package-lock.json은 생성되지 않았다.
- 사용자가 되돌리기를 승인하여 초기 설정 파일 12개를 제거했다. Constitution·Spec·Plan·Tasks·Skills는 보존했다.
- 향후 구현은 명세·계획·작업 목록을 제시한 뒤 사용자의 명시적 승인을 받고 시작한다.
- 기존 Plan/Research의 버전 조합은 설치 호환성이 확인된 상태가 아니다. 재구현 전에 위 충돌을 기술 계획에 반영하고 관련 조합을 다시 검증해야 한다.
- Application Build·Type Check·Lint·Unit·Integration·Acceptance는 수행하지 않았다.

## 2026-09-07 — 아이디어 보완과 문서 정합성 재검토

- 사용자 요청: 앞선 아이디어 검토의 허점을 원래 AgentFit 기획 안에서 보완. 애플리케이션 구현 승인은 포함하지 않는다.
- PRD에 환경 증거 수준, 추가 도구 불필요 결과, 실제 권한 변환의 지원 범위, Catalog 포함관계·조합·고정 실행 템플릿, 적용·인증·무해한 사용 확인 안내, 최소 이력 보관과 승인 무효화 조건을 반영했다.
- `Docs/validation-plan.md`에 V1–V7의 표본·방법·판정·기본 담당을 정했다. 사용자 인터뷰·기존 방법 비교·권한/조합·실제 AI 평가는 모두 미수행이다.
- 루트 Agent.md와 다섯 역할의 배포 문서·README를 동기화했다. 역할 문서의 공통 1–5·8–10절은 동일하며 개인 PC 경로·과거 설치 이력은 포함하지 않는다. 루트에 삭제 요청한 12절을 복원하지 않았다.
- 기존 Feature를 유지하는 Specify 수정 경로로 공식 `resolve-template.ps1 spec-template -Json`을 실행했다. 새 Feature·Branch를 생성하거나 기존 명세를 템플릿으로 초기화하지 않았다.
- FR-010–012의 의미 판단·근거 위치 설명을 구체화하고 SC-011 의미 사례와 SC-012 정상 첫 요청 성공률을 추가했다. 기존 사용자 Clarification 5개와 SC-001–010은 유지한다.
- 영향받는 Plan·Tasks·Research·Data Model·HTTP Contract·Quickstart를 수동으로 정합화했다. 전체 plan/tasks 생성 Workflow를 다시 실행한 것으로 보고하지 않는다.
- 과거 설치 충돌에 따라 Plan은 Vitest 5를 제외하고 4.x 범위로 정정했다. 정확한 patch·engine/peer 조합 확인과 고정은 구현 승인 후 T001에서 수행한다. 새 설치·호환성 실측은 하지 않았다.
- 요구사항 품질 체크리스트 16/16, Security/UX 체크리스트 20/20을 수정된 명세에 재대조했다. 체크는 문서 품질 상태이며 구현·테스트 통과가 아니다.
- Spec Kit Analyze: 공식 `check-prerequisites.ps1 -Json -RequireSpec -RequireTasks -IncludeTasks` 성공 후 읽기 전용 분석 수행. FR 24개 + SC 12개 = 36개 모두 작업에 연결된다. SC-007 사람 대상 평가는 T044에 별도로 연결하며 구현 가능한 분석 분모 35개도 100% 연결된다.
- Tasks는 T001–T046 총 46개이며 모두 미완료다. 공통 기반·문서·품질 작업까지 목적에 연결했고 누락 Task ID·존재하지 않는 연결 Task·중복 Task ID는 없다.
- 최초 재분석에서 I1(HIGH: Plan의 배포 범위 제외와 T045 운영 보관 검증의 충돌), A1(LOW: FR-010 확정값 누락 문구)을 발견했다.
- 읽기 전용 분석 종료 후 이미 승인된 문서 보완 범위에서 두 항목을 수정했다. 공개 배포·배포 자동화와 배포 예정 호스트의 필수 보관 검증을 구분하고, 문맥상 확정된 사실을 미정으로 누락하지 않는다고 정리했다.
- 영향 항목 재대조 결과 I1·A1을 해결했으며 남은 CRITICAL/HIGH 불일치와 미연결 필수 요구는 발견하지 못했다. 이는 실행 가능성·보안·성능의 실측 보장이 아니다.
- PRD 기능 요구 정의 PRD-01–41의 고유성, 내부 문서 링크, 역할 공통 정책, 기존 사용자 답변 유지와 구현 작업 미체크 상태를 확인했다. 검토 보고서의 F01–F10을 반영한 요구와 V1–V7에 연결했다.
- Analyze 전후 `.specify/extensions.yml`은 없으며 실행할 extension hook이 없다. Constitution 1.0.0은 변경하지 않았다.
- Application Source·Config·Test 생성, 패키지 설치, Build·Type Check·Lint·Unit·Integration·실제 Acceptance·사용자 모집은 수행하지 않았다.


## 2026-09-08 — 팀 API 명세 추가 (문서 검증만 수행)

- Docs/api에 공통 규칙·첫 Feature 상세·OpenAPI 3.1 JSON·후속 추천 초안·후속 권한/설정 초안·목차를 작성했다. 기획서·공통/역할 PRD·배포 안내에서 연결했다.
- 첫 Feature HTTP·Data Model·Plan·Tasks·Research에 공개 인증 DTO/allowlist, 정확한 필드·오류, Profile 버전/출처, 동시 실행 슬롯 확보 순서를 동기화했다. 기존 사용자 Clarification·FR/SC와 개발 순서는 유지한다.
- 문서 전용 임시 검사로 OpenAPI JSON 파싱, 로컬 $ref 156개, 고유 operation 7개/경로 5개, schema 21개, 요청/응답 예시 21개를 대조했다. 사용한 type·required·additionalProperties·nullable·배열/문자 경계·enum·dependentRequired·조합 키워드 검사에서 오류를 발견하지 못했다.
- 합성 잘못된 요청 6개는 추가 ownerId, 필드 누락, draft ID/version 쌍 누락, 삭제 미확인, 공개 Session token 추가를 포함하며 모두 schema 수준에서 거부됐다. Profile 예시 6곳의 null/unknownFields/출처/근거 대응을 확인했다.
- 전용 OpenAPI/JSON Schema 검증 패키지를 설치하지 않았다. 위 검사는 실제 사용한 제약을 대상으로 한 정적 대조이며 전체 OpenAPI 메타스키마 인증이나 런타임 계약 테스트가 아니다. bytes·PDF·소유권·원문 의미·DB 경쟁·인증 쿠키는 실제 구현 후 검증한다.
- Docs와 Feature Markdown의 로컬 파일 링크에서 누락을 발견하지 못했고, 새 API 문서에 개인 PC 경로·RTK 지침을 포함하지 않았다.
- T001–T046은 46개 모두 미완료로 유지했다. 애플리케이션 소스/설정/테스트 생성, 패키지 설치, Build·실제 API 호출·DB·OAuth·Provider·브라우저 테스트는 수행하지 않았다.
