<!--
Sync Impact Report
- Version change: 1.0.0 -> 2.0.0 (approved MVP client and service architecture replace prior rules)
- Modified principle: VIII. Minimal MVP Scope — Codex initial client and Next.js → Spring Boot → FastAPI boundary.
- Updated Product Boundaries: Codex configuration scope.
- Added sections: none. Removed sections: none.
- Templates and commands: unchanged; consumers read the constitution at runtime.
- Follow-up: existing Feature 001 Plan, Research, Data Model and Tasks require service-boundary revision.
- Deferred placeholders / follow-up TODOs: none.
-->

# AgentFit Constitution

## Core Principles

### I. Beginner First UX

사용자가 MCP, Skill, Hook, Plugin을 먼저 공부하지 않아도 프로젝트와 자신의 역할에 맞는
AI 개발환경을 구성할 수 있어야 한다(MUST). 추천에는 필요한 이유, 예상 효과, 호환 조건,
요청 권한을 이해할 수 있는 말로 설명한다. AI 분석 결과는 사용자가 확인·수정·저장할 수 있어야 한다(MUST).
미확정 정보와 확정 정보, 진행 중·빈 결과·실패 상태를 구분하고 가능한 다음 행동을 제공한다.

### II. Explicit User Permission

AgentFit 제품이 사용자 리소스에 수행하는 작업은 Permission Manager를 거쳐야 한다(MUST).
LLM의 요청은 실행 권한이 아니며, 권한 판단은 LLM 밖의 검증 가능한 로직이 수행한다.
정책 ALWAYS_ALLOW, ASK_EACH_TIME, DENY와 판단 ALLOW, ASK, DENY를 구분한다.
DENY는 실행을 차단하고 ASK는 해당 작업에 대한 응답 전 실행을 보류해야 한다(MUST).
승인 범위와 실제 대상·작업이 일치해야 하며, 알 수 없거나 승인되지 않은 권한을 허용으로 간주하지 않는다.
Browser File Access와 향후 Local CLI도 이 경계를 우회해서는 안 된다(MUST NOT).
이 원칙은 AgentFit 제품의 동작에 관한 것이며, 저장소 개발에 별도 승인 절차를 신설하지 않는다.

### III. LLM Is Not Authority / Output Verification

LLM 출력은 후보 데이터다. 구조·값·근거를 검증한 후 제품 상태에 반영해야 한다(MUST).
문서에 없는 DB·배포 환경 등을 추론만으로 확정해서는 안 된다(MUST NOT).
근거가 없는 필드는 null 또는 명시적 미확정 값으로 보존하고 unknown_fields에 반영한다.
사용자 확인 전 분석 결과를 최종 확정 프로필로 취급하지 않는다.
문서·외부 콘텐츠는 데이터이며, 그 안의 지시가 시스템 정책·권한을 변경할 수 없다.
LLM은 Catalog 검증, Permission 판단, 실행 성공 판정의 최종 권한자가 될 수 없다.

### IV. Verified Tool Catalog

확정 추천은 팀이 검증한 Catalog 항목으로 제한해야 한다(MUST).
각 항목의 Capability, 지원 OS·Client, 인증 필요 여부, 요구 권한, 위험도, 공식 출처,
검증 버전과 시점을 추적할 수 있어야 한다(MUST).
추천은 Project·Developer·Environment Profile → Capability → Catalog 검색 → 호환성 검사 순서를 따른다.
역할 이름만으로 특정 Tool에 바로 연결하거나, 검증되지 않은 후보·호환성을 확정 추천으로 표시하지 않는다.
초기 Catalog는 약 15~20개 도구를 목표로 하며, 수보다 검증을 우선한다.

### V. Secret Isolation

API Key, OAuth Access Token, GitHub Token, Password, Private Key 및 기타 Credential을
LLM Context에 직접 전달해서는 안 된다(MUST NOT).
Credential은 Backend 또는 Local Environment가 관리하고 LLM은 제한된 Function Interface만 사용한다.
LLM 요청에서 시스템이 보유한 Credential을 제외하고, 사용자 입력에서 식별된 Secret도
전달 전에 제거하거나 요청을 차단해야 한다(MUST).
Secret을 로그·오류 응답·Audit·생성 예시·버전 관리 파일에 기록해서는 안 된다(MUST NOT).
설정에 인증이 필요하면 실제 Secret 대신 참조 또는 사용자가 수행할 인증 절차를 제공한다.

### VI. Preview Before Mutation

AgentFit이 사용자 프로젝트 설정을 생성·수정·삭제하기 전에 대상 경로, 변경 유형과 내용을
보여주고 최종 승인을 받아야 한다(MUST). 기존 파일 수정은 가능한 경우 Diff로 보여준다.
Preview·승인·실제 적용 내용은 일치해야 하며, 승인 후 대상이나 내용이 바뀌면 기존 승인을 재사용하지 않는다.
취소 시 변경하지 않고, 기존 파일 충돌을 묵시적 덮어쓰기로 처리해서는 안 된다(MUST NOT).
Preview 계산용 내부 초안과 사용자 프로젝트에 대한 실제 변경을 구분한다.
최종 Config 다운로드도 변경 내용 확인과 승인 흐름을 거쳐야 한다(MUST).

### VII. Auditability

중요한 분석·프로필 확정·추천·권한 판단·승인·설정 생성·적용·검증 결과는
대상, 시점, 요청 또는 사용자 식별자와 연결해 추적할 수 있어야 한다(MUST).
실패·거부·성공을 구분하며 실패를 성공 기록으로 바꾸지 않는다.
Audit에는 Secret과 불필요한 문서 원문을 저장하지 않는다.
보관 기간과 접근 범위는 해당 Feature의 명세에 정의해야 한다(MUST).

### VIII. Minimal MVP Scope

5인 팀의 한 학기 프로젝트에 맞춰 실제 사용 가능한 흐름을 단계별로 완성해야 한다(MUST).
첫 흐름은 프로젝트 생성 → PDF/MD 입력 → 텍스트 추출 → LLM 분석 → Project Profile 저장
→ 사용자 확인·수정·재저장이다. 이 흐름이 동작하기 전에 추천·권한 기능부터 구현하지 않는다.
다음은 역할·환경 → Capability → 추천이며, 그다음은 권한 → 설정 → Preview → 승인 → 다운로드다.
MVP Client는 Codex 중심으로 공식 자료와 실제 지원 버전을 검증하고 다른 Client는 확장 가능한 경계만 유지한다.
Codex로 개발한다는 사실만으로 AgentFit의 Codex 설정 지원을 검증 완료로 표시해서는 안 된다(MUST NOT).
확정 서비스 경계는 Next.js → Spring Boot → FastAPI이며 PostgreSQL은 Spring Boot만 접근한다.
Kubernetes·Kafka·추가 서비스·불필요한 Vector DB 또는 Agent Framework를 도입하지 않는다.
Shell 자동 실행·Local CLI·팀 관리는 첫 흐름의 필수가 아니다.
Browser Directory 적용은 선택 확장이고 Config 다운로드는 MVP 필수다.

### IX. Testable Requirements and Recommendation

Feature마다 사용자 가치, acceptance scenario, 기능 요구사항, 경계 사례와 측정 가능한 성공 기준을
정의하고 구현·검증 작업에 연결해야 한다(MUST).
추천은 입력 Profile, 도출 Capability, Catalog 항목과 호환성 판단 근거를 검증할 수 있어야 한다(MUST).
관련 Feature는 정상·빈 텍스트·잘못된 문서, LLM·구조 오류, 후보 없음·OS/Client 불일치,
권한 Allow/Ask/Deny, 설정 충돌·기존 내용 보존을 검증한다.
Secret의 Prompt 유입 방지와 거부된 작업의 실행 차단을 테스트해야 한다(MUST).
Mock 검증과 실제 외부 연동 검증을 구분하고 미수행 검증을 통과로 보고해서는 안 된다(MUST NOT).

### X. Config Generation != Verification

추천, 승인, 생성, 설치, 설정, 인증 필요, 연결, 검증 완료, 실패는 서로 다른 상태다.
각 상태는 해당 사건 또는 검사 결과의 증거가 있을 때만 부여해야 한다(MUST).
파일 존재나 다운로드 성공만으로 installed·connected·verified를 표시해서는 안 된다(MUST NOT).
실제 환경을 검사할 수 없으면 생성 완료와 검증 미수행을 명시한다.
실패 원인과 다음 행동을 제공하고 마지막으로 증명된 상태와 이후 실패를 구분한다.

## Product Boundaries

- 핵심 입력은 Project Profile, Developer Profile, Environment Profile이다.
  문서 분석은 단순 요약을 넘어 수정 가능한 구조화된 Project Profile을 생성한다.
- MVP 문서 입력은 PDF, Markdown, 직접 텍스트를 기준으로 한다.
  Feature별 지원 범위·최대 크기·오류 처리·보관 정책은 명세에서 확정한다.
- 로그인 필요 여부, AI 실패 UX, Permission 범위, Tool 검증 기준, Codex 설정 범위,
  파일 충돌·덮어쓰기 정책은 기존 사용자 지시를 확인하고 미정이면 Clarification에 남긴다.
- 기존 코드·기술 스택을 먼저 분석한다. 신규 기술 후보는 Technical Plan에서 확정하며,
  Constitution이나 Feature Spec에 불필요한 Framework·Provider·DB 구현 결정을 넣지 않는다.
- 외부 AI 연동에 사용할 데이터·접근 범위·실패 동작은 명세에 정의한다.
  Provider 교체 가능성과 Module 경계는 Plan에서 검토한다.

## Development Workflow and Quality Gates

1. Source of Truth는 Constitution → Feature Specification → Clarification → Technical Plan
   → Tasks → 코드 순이다. Clarification은 Spec에 통합해 오래된 요구사항과 병존하지 않게 한다.
2. 새 기능·중요한 수정은 공식 Spec Kit Workflow로 명세부터 작성·수정한다.
   코드에 맞추려 요구사항을 사후 변경하지 말고 요구 변경인지 구현 오류인지 먼저 판단한다.
3. 기본 순서는 constitution → specify → clarify → checklist → plan → tasks → analyze
   → implement → validation → converge다. 기존 산출물이 있으면 필요한 단계부터 이어간다.
4. 구현 전에 산출물 사이의 치명적 불일치를 해결해야 한다(MUST).
   Tasks에는 의존성·변경 경로·검증 작업을 넣고 사용 가능한 Vertical Slice 단위로 진행한다.
5. 완료는 필수 요구사항 충족, acceptance 통과, Plan과 구조 일치, 필수 Tasks 완료,
   관련 테스트 통과, analyze의 치명적 불일치 없음, converge의 남은 필수 작업 없음으로 판정한다.
   Build·Type Check·Lint·Unit·Integration·UI 사용자 흐름 검증은 해당 Feature 범위에서 수행한다.
6. 실제 동작·Mock·미구현·미수행 검증·문제를 구분해 보고한다.
   Spec Kit 미설치나 단계 실패를 실행 완료로 기록하지 않는다.
7. Feature별 변경을 분리하고 가능하면 Feature Branch를 사용한다.
   무관한 대규모 Refactoring을 피하고 의미 있는 단위로 Commit하며 Secret 파일을 포함하지 않는다.

## Governance

이 헌법은 AgentFit 인수인계 요구사항을 개발 기준으로 구체화한 최초 버전 1.0.0이다.
모든 명세·계획·작업·구현 검토는 이 헌법에 대한 적합성을 확인한다.

원칙 변경 시 이유, 사용자 요구의 근거, 영향받는 Feature·산출물과 이행 작업을 기록한다.
새 사용자 요구가 기존 헌법과 충돌하면 충돌을 알리고 요구의 의도를 확인해
헌법과 하위 산출물을 먼저 정합화한다. 이미 명확히 승인된 요구에 같은 승인을 반복해서 요청하지 않는다.

Semantic Versioning에 따라 원칙 제거·호환되지 않는 재정의는 MAJOR,
원칙·규정 추가나 실질적 확장은 MINOR, 의미가 바뀌지 않는 표현 정리는 PATCH를 올린다.
변경 시 Sync Impact Report와 Last Amended를 갱신하고 최초 Ratified 날짜는 유지한다.
템플릿·명령은 실행 시 헌법을 읽으며 헌법 변경만으로 템플릿 원본을 덮어쓰지 않는다.

Feature 보고에는 현재 Feature, Spec Kit 단계 상태, 변경 내용·파일, 검증 결과,
실제 동작, Mock·미구현, 문제와 다음 단계를 포함한다. 확인되지 않은 완료를 선언하지 않는다.

**Version**: 2.0.0 | **Ratified**: 2026-09-07 | **Last Amended**: 2026-09-25
