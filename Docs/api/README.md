# AgentFit API 명세

> 기준일: 2026-09-08 · 팀 설계·화면/서버 계약 공유용 · API 구현 전

## 1. 어떤 문서를 쓰면 되는가

| 문서 | 범위 | 상태 |
| --- | --- | --- |
| [공통 규칙](common.md) | 인증·접근 제어·오류·버전·보관·재시도 | 첫 Feature의 상세 계약 |
| [프로젝트·문서 분석](01-project-analysis.md) | 개인 프로젝트·raw 문서 입력·초안·확인 저장·삭제 | 현재 Feature 설계와 동기화 |
| [OpenAPI 3.1 JSON](openapi.phase1.json) | 공개 세션 조회 + 프로젝트 API 7개 operation의 schema·예시 | 첫 Feature 명세, 실제 서버 아님 |
| [역할·환경·추천](02-recommendations.draft.md) | Developer/Environment Profile·Catalog·네 가지 추천 결과 | 후속 DESIGN DRAFT |
| [권한·설정·다운로드](03-configuration.draft.md) | 선택·Preview·최종 승인·ZIP·최소 이력·사용자 진술 | 후속 DESIGN DRAFT |

첫 Feature는 `001-project-document-analysis`다. 세션 조회 1개와 프로젝트 도메인 6개 operation을 OpenAPI로 제공한다.
GitHub 로그인 시작·callback·로그아웃은 Better Auth SDK 프로토콜이며 [공통 규칙](common.md)에 허용 경로와 응답 노출 기준을 명시했다.
SDK 프로토콜을 도메인 API의 error envelope로 바꾸지 않는다.

후속 API의 경로·DTO·한도·만료 시간은 함께 검토할 설계안이다. 후속 Feature 명세·작업과 실제 지원 조합을 확정하기 전에 구현 완료 계약으로 취급하지 않는다.
첫 Feature의 미구현 상태와 사용자 승인 대기 원칙도 그대로 유지한다.

## 2. 전체 API 지도

| 단계 | Method | 경로 | 목적 |
| --- | --- | --- | --- |
| 현재 | GET | /api/auth/get-session | 안전한 화면용 세션 또는 null |
| 현재 | GET / POST | /api/projects | 내 프로젝트 목록 / 생성 |
| 현재 | GET / DELETE | /api/projects/{projectId} | 상세 / 확인 후 삭제 |
| 현재 | POST | /api/projects/{projectId}/analysis | raw PDF·Markdown·텍스트 분석 |
| 현재 | PATCH | /api/projects/{projectId}/profile | 전체 Profile 확인 저장 |
| 후속 초안 | GET / PUT | /api/projects/{projectId}/developer-profile | 역할·주요 업무·경험 |
| 후속 초안 | GET / PUT | /api/projects/{projectId}/environment-profile | 사용자 진술에 따른 환경 |
| 후속 초안 | GET | /api/tool-catalog | 검증 범위가 표시된 소규모 Catalog |
| 후속 초안 | POST | /api/projects/{projectId}/recommendations | 현재 입력으로 추천 판단 |
| 후속 초안 | GET | /api/projects/{projectId}/recommendations/latest | 최신 결과와 오래됨 여부 |
| 후속 초안 | POST | /api/projects/{projectId}/config-previews | 선택·권한 검사 및 내용 비교 |
| 후속 초안 | POST | /api/projects/{projectId}/config-approvals | 특정 Preview에 최종 승인 |
| 후속 초안 | POST | /api/projects/{projectId}/config-exports | 승인과 일치하는 파일 다운로드 |
| 후속 초안 | GET | /api/projects/{projectId}/configuration-history | 원문 없는 생성 이력 |
| 후속 초안 | POST | /api/projects/{projectId}/configuration-history/{configurationId}/reports | 사용자 적용 결과 진술 |

## 3. 화면에서 서버로 연결하는 순서

```text
세션 확인 → GitHub 로그인 → 프로젝트 생성/조회
→ raw 입력 POST → DRAFT 표시 → 사용자 수정
→ Project.version + 선택한 DRAFT의 id/version으로 확인 저장
→ 프로젝트 상세 재조회

[후속]
확인 Project + 역할/환경 저장 → 추천 생성
→ 추천 결과에 따른 정보 보완 또는 도구 선택
→ 지원 권한 정책 선택 → Preview → 최종 승인
→ 같은 입력으로 승인 내용 재검증 → ZIP 다운로드
→ 적용/인증/무해한 사용 확인 안내
```

- multipart 업로드, JWT 본문 전달, 원문 재조회, 분석 202 job polling은 첫 계약에 없다.
- null은 미정, []는 명시적 없음이다. AI 초안과 사용자 확인 Profile을 분리한다.
- 저장에는 Project.version, 초안 확인에는 draftId/draftVersion까지 필요하다.
- 후속 NO_ADDITIONS_NEEDED는 정상 결과다. 새 도구를 억지로 생성하지 않는다.
- 기존 파일이 없거나 미확인인 상태를 실제 PC 검사 완료로 해석하지 않는다.
- Preview의 내용을 보관하지 않으므로 재접속 후에는 필요한 입력을 다시 제공한다.
- 설정 생성·사용자 적용 진술을 시스템 검증 완료로 표시하지 않는다.

## 4. 파트별 읽을 범위

| 파트 | 필수 확인 | 인계할 결과 |
| --- | --- | --- |
| Full Stack A | 공통·첫 Feature·OpenAPI, 후속 저장/접근 제어 | 안전한 DTO·HTTP·DB 트랜잭션 경계 |
| Full Stack B | 추천·권한/설정 초안, 공통 | 검증 Catalog·정책 매핑·생성/승인 계약 |
| AI Developer | 첫 Profile 필드/출처/근거·오류, 추천 Capability | 입력/출력 schema·의미 검증·실패 분류 |
| Frontend Developer | 전체 사용자 흐름·DTO·오류·버전 | 화면/API 대응·충돌/실패 복구·다운로드 |
| Designer | 상태표·미정/없음·네 추천 결과·승인/검증 경계 | 화면과 다음 행동이 맞는 상태·문구 |

파트별 책임과 수용 기준은 [역할별 PRD](../team-prds/README.md)를 따른다.
필드 이름을 화면이나 모듈별로 새로 정하지 말고 계약 변경을 A와 해당 파트가 함께 반영한다.

## 5. 사용·변경 규칙

OpenAPI 파일을 팀의 로컬 OpenAPI 3.1 지원 도구에 불러와 schema와 예시를 볼 수 있다.
문서 자체가 mock 서버를 제공하거나 실제 endpoint의 동작을 증명하지는 않는다.
분석 입력 중 PDF는 binary body이며 본문 schema만으로 실제 PDF 페이지·의미·Secret 검사를 대체할 수 없다.
JSON Schema 검증 외에 bytes·code points·근거 범위·출처·버전·소유권 같은 업무 규칙을 확인한다.

변경 시 첫 Feature [HTTP 계약](../../specs/001-project-document-analysis/contracts/http.md)·[데이터 모델](../../specs/001-project-document-analysis/data-model.md)·Plan·Tasks와 이 문서/OpenAPI를 함께 수정한다.
문서 우선순위는 Constitution → Feature Spec·Clarification → Plan → Tasks → 코드이며 API 문서는 해당 기술 계약을 상세화한 것이다.
후속 계약을 먼저 구현하라는 지시로 해석하지 않는다. 실제 애플리케이션 구현은 범위를 제시하고 사용자 승인 후 시작한다.

[팀 기획서](../project-proposal.md) · [공통 PRD](../PRD.md) · [검증 실행 계획](../validation-plan.md)
