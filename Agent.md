# AgentFit 개발 에이전트 지침

> 2026-09-25 확정: Next.js → Spring Boot → FastAPI. PostgreSQL은 Spring Boot만 접근하고 AI Developer는 FastAPI의 추출·분석·검증·평가를 맡는다. 실패 건에서 실제 수신한 LLM 원본 응답만 최대 7일 진단용으로 보관한다. 기존 단일 Next.js 서버 Plan·Tasks는 재계획 전까지 구현 기준이 아니다.

이 문서는 AgentFit의 원래 개발 인수인계 기획과 사용자가 확정한 요구사항을 정리한다.
별도로 제안했던 Startup Canvas 전략은 채택하지 않으며 제품 범위와 개발 기준에 반영하지 않는다.
상세 요구사항과 구현 계획의 기준은 아래에 연결된 Spec Kit 산출물이다.

## 1. 구현 전 사용자 승인

사용자의 명시적 지시: **“구현 전엔 물어봐.”**

- 애플리케이션 구현을 시작하기 전에 대상 Feature, 명세, 계획, 작업 범위와 미해결 문제를 제시하고 명시적 승인을 받는다.
- 기획 논의, 문서 생성, 명세 검토 요청을 구현 승인으로 해석하지 않는다.
- 승인 전에는 애플리케이션 소스·설정·테스트 코드를 생성하거나 의존성 설치 등 초기 구현 작업을 시작하지 않는다.
- 승인받은 범위에서는 작업을 이어가되, 새로운 Feature나 중요한 범위 변경은 관련 문서를 정리한 뒤 구현 승인을 받는다. 동일한 범위에 이미 받은 승인을 반복해서 묻지 않는다.
- 이 개발 승인 규칙은 AgentFit 제품 내부의 Permission Manager와 별개의 사용자 지시다.
- 현재 이 문서의 생성은 승인된 문서 작업이며, 애플리케이션 구현 승인은 아니다.

## 2. 제품 정의와 목표

**AgentFit: 기획서와 역할에서 출발해 개발환경을 확인하고, 프로젝트에 맞는 AI 설정을 추천·생성·적용 안내하는 웹 서비스.**

개발 초보자가 MCP, Agent Skill, Hook, Plugin, Project Rules와 도구별 설정을 먼저 공부하지 않아도 자신의 프로젝트에 맞는 구성을 선택할 수 있게 한다.
필요한 이유, 호환성, 설치·설정 방법, 요구 권한과 변경 내용을 이해할 수 있게 보여준다.

기본 입력은 프로젝트 기획서, 사용자 역할, 기술 스택, 사용하는 AI 개발 도구와 허용할 권한 범위다.
문서에서 확인할 수 없는 정보는 추가 질문이나 사용자의 수정으로 보완한다.

최종 목표는 다음 흐름을 실제로 완성하는 것이다.

```text
기획서 입력 → 프로젝트 이해 → 사용자 역할·환경 이해
→ 필요한 Capability 추출 → 검증된 도구 추천
→ 구성 선택·권한 확인 → 설정 초안·변경 Preview
→ 사용자 최종 승인 → Config 생성·다운로드 또는 허용된 범위에 적용
→ 확인 가능한 근거에 따른 상태 표시
```

기능 수보다 이 흐름의 완성을 우선한다.

## 3. 개발 기준 문서

Spec Kit 산출물의 우선순위는 다음과 같다.

1. [Constitution](.specify/memory/constitution.md)
2. [Feature Specification](specs/001-project-document-analysis/spec.md)
3. 해당 Spec에 통합된 Clarification 결과
4. [Technical Plan](specs/001-project-document-analysis/plan.md)
5. [Tasks](specs/001-project-document-analysis/tasks.md)
6. 실제 구현 코드

이 문서는 위 산출물을 대체하는 별도 명세가 아니다. 최신 사용자 지시는 우선 반영하며 기존 문서와 충돌하면 영향과 변경 필요성을 알린다.
코드와 Spec이 다르면 요구사항 변경인지 구현 오류인지 먼저 판단한다. 구현 결과에 맞추려고 Spec이나 정답 데이터를 사후 수정하지 않는다.

관련 자료:

- [팀 공통 PRD](Docs/PRD.md)
- [검증 실행 계획](Docs/validation-plan.md)
- [역할별 배포 문서](Docs/team-agents/README.md)
- [저장소 초기 조사](Docs/repository-assessment.md)
- [기술 조사](specs/001-project-document-analysis/research.md)
- [데이터 모델](specs/001-project-document-analysis/data-model.md)
- [HTTP 계약](specs/001-project-document-analysis/contracts/http.md)
- [개발·검증 준비 절차](specs/001-project-document-analysis/quickstart.md)
- [요구사항 체크리스트](specs/001-project-document-analysis/checklists/requirements.md)
- [보안·UX 체크리스트](specs/001-project-document-analysis/checklists/security-ux.md)
- [검증 및 구현 승인 대기 기록](specs/001-project-document-analysis/validation.md)

## 4. 반드시 지킬 제품 원칙

1. **Beginner First UX**: 전문 용어보다 필요한 이유와 다음 행동을 설명한다. 진행·빈 상태·실패·미확정을 구분한다.
2. **Explicit User Permission**: 사용자 리소스에 대한 작업은 권한 검사를 거친다. 거부나 응답 대기를 허용으로 취급하지 않는다.
3. **LLM Is Not Authority**: AI 출력은 검증할 후보 데이터다. 문서 지시를 실행하거나 AI가 권한·성공 여부를 최종 결정하게 하지 않는다.
4. **Verified Tool Catalog**: 검증된 Catalog와 호환성 검사에 통과한 도구만 확정 추천한다.
5. **Secret Isolation**: API Key, OAuth Token, GitHub Token, Password, Private Key를 LLM Context에 전달하지 않는다.
6. **Preview Before Mutation**: 변경할 경로·유형·내용을 보여주고 최종 승인을 받는다. 기존 파일 수정에는 가능한 경우 Diff를 제공한다.
7. **Auditability**: 중요한 분석·추천·권한·설정 처리의 대상, 시점, 결과를 추적한다. 원문과 Secret을 감사 기록에 담지 않는다.
8. **Minimal MVP Scope**: 5인 팀의 한 학기 범위에서 사용 가능한 흐름을 순서대로 완성한다.
9. **Testable Requirements and Recommendation**: 요구사항과 추천 근거를 테스트 가능한 형태로 만들고 실제 결과로 검증한다.
10. **Config Generation != Verification**: 파일 생성·다운로드를 설치·연결·동작 검증 완료로 표시하지 않는다.

## 5. MVP 범위와 개발 순서

MVP 필수 범위는 프로젝트 생성, PDF·Markdown·직접 텍스트 입력, Project Profile 분석·수정, 역할·환경 입력, Capability 추출, Tool Catalog, 추천, 권한 설정, Config 생성, 변경 Preview, Config 다운로드와 적용·인증·무해한 사용 확인 안내다.

### 첫 번째 흐름: 프로젝트와 문서 분석

```text
GitHub 로그인 → 프로젝트 생성·목록·상세
→ PDF/Markdown 업로드 또는 텍스트 입력 → 텍스트 추출
→ LLM 분석 → 검증된 Project Profile 초안 저장
→ 분석 결과 확인·수정 → 사용자 확인 프로필 저장 → 재접속 확인
```

현재 Feature는 `001-project-document-analysis`다. 원래 기획의 Project Foundation과 Project Document Analysis를 첫 흐름의 선행 기반 및 핵심 기능으로 함께 계획했다.
보관 정책을 충족하는 최소 프로젝트 삭제 기능도 포함한다.
이 흐름이 실제로 동작하기 전에 Recommendation이나 제품 Permission Manager부터 구현하지 않는다.

### 두 번째 흐름: 역할과 환경에 맞는 추천

```text
Project Profile → Developer Profile → Environment Profile
→ Capability → Catalog 검색 → Compatibility 검사
→ Tool Recommendation → 추천 이유·요구 권한·위험도 표시
```

### 세 번째 흐름: 승인과 설정 다운로드

```text
Recommendation 선택 → Permission 확인·승인
→ Config 초안 생성 → Change Preview → 사용자 최종 승인
→ 승인한 내용의 Config 생성·다운로드
```

Preview용 내부 초안과 최종 산출물·프로젝트 파일 변경을 구분한다. 승인된 내용과 실제 산출물은 일치해야 한다.

세부 Feature 순서는 Foundation → Document Analysis → Developer/Environment Profile → Capability Analyzer → Tool Catalog → Recommendation → Permission Manager → Config Generator → Change Preview → Export/Apply → Environment Status다.
각 단계에서 새 명세가 필요한 범위를 먼저 정리한다.

### 지원 범위와 후속 확장

- 초기 Client는 **Codex 중심**으로 검증한다. AGENTS.md, Skill, MCP와 설정·Plugin·Hook의 지원 범위는 공식 자료와 실제 버전별 검증으로 확정한다.
- Claude Code, VS Code Agent, Cursor 등은 이후 Client Adapter 확장 후보이다. Codex로 개발한다는 이유만으로 제품의 Codex 설정·연결 검증이 완료된 것은 아니다.
- 사용자가 선택한 폴더에 대한 Browser File System Access 적용은 선택 기능이며, Config 다운로드가 MVP 필수다.
- Shell 자동 실행은 MVP 필수가 아니다. Local CLI와 명령 실행·백업·복원·환경 검사는 후속 확장이다.
- Team·TeamMember는 장기 Entity 후보이며 첫 Feature에서 팀 공유를 구현하지 않는다.
- OCR, 이미지·표의 시각적 의미 해석, 여러 문서 병합 분석은 첫 Feature 범위 밖이다.

## 6. 첫 Feature에서 확정한 사용자 결정

아래 사항은 이미 답변받았으므로 변경 요청이나 새로운 충돌이 없는 한 다시 질문하지 않는다.

| 항목 | 확정 요구사항 |
| --- | --- |
| 인증 | GitHub 계정 로그인만 제공한다. 사용자 식별 목적이며 저장소 권한은 요청하지 않는다. |
| 접근 범위 | 로그인 필수, 본인 소유 프로젝트만 조회·분석·수정·삭제할 수 있다. 직접 API 요청에도 동일하게 적용한다. |
| 입력 | PDF, Markdown 파일 또는 직접 입력 텍스트. 한 분석 요청에는 하나의 입력을 사용한다. |
| 파일 한도 | 최대 10 MiB, 즉 10,485,760 bytes. |
| PDF 한도 | 최대 100쪽. |
| 텍스트 한도 | 추출·직접 입력 텍스트 최대 100,000 Unicode code points. 공백·줄바꿈을 포함한다. |
| 경계 처리 | 한도와 정확히 같은 유효한 입력은 허용한다. 초과분을 몰래 잘라 분석하지 않는다. |
| AI 실패 복구 | 기존 저장 프로필을 보존하며 재시도와 직접 작성·수정을 모두 제공한다. |
| 원문 보관 | AgentFit이 관리하는 원문·추출문은 처리 중에만 사용하고 처리 종료 후 보관하지 않는다. 재분석에는 입력을 다시 제출한다. |
| 결과 보관 | 프로필·최소 문서 정보·분석 시도·감사 기록은 프로젝트 삭제 시 함께 삭제한다. |

보관 원칙은 성공뿐 아니라 실패·시간 초과·취소·비정상 종료에도 적용한다.
AgentFit의 삭제를 외부 AI 서비스의 삭제 보장으로 설명하지 않는다. 외부 AI로 전달할 내용과 별도 처리 조건을 고지한다.

## 7. Profile과 추천 설계

### Project Profile

문서 분석은 단순 요약이 아니라 다음 항목의 구조화다.

- 프로젝트명, 유형, 도메인
- Frontend, Backend, AI 기술
- Database, 배포 환경
- 핵심 기능, 외부 연동
- 미확정 항목과 값의 출처

문서에 없거나 상충하는 정보는 `null` 및 미확정 목록으로 표현한다. 후보 기술을 확정값으로 바꾸지 않는다.
배열의 `null`은 미정, 빈 배열은 명시적으로 없음이라는 의미를 구분한다. 실제 필드명과 API 형태는 데이터 모델·계약을 따른다.

AI 분석 초안과 사용자 확인 프로필을 구분하고 모든 항목을 사용자가 수정할 수 있게 한다.
미확정 항목이 남아 있어도 사용자 확인·저장은 가능하다. 확인 여부와 정보 완전성을 구분한다.
재분석은 기존 확인 프로필을 덮어쓰지 않는다. 동시 수정·늦은 분석 응답이 최신 저장을 묵시적으로 변경하거나 삭제된 프로젝트를 되살리지 않도록 한다.
분석값은 처리 중 원문 근거와 대조하고 저장 시에는 필요한 근거 위치를 남긴다. 원문 인용 구절을 계속 저장하지 않는다.

### Developer / Environment Profile

Developer Profile은 역할, 주요 업무, 개발 경험을 수집한다. 역할 후보는 Frontend, Backend, Full Stack, AI, Designer다.
Environment Profile은 OS, AI Coding Client와 런타임 버전, 기술 스택, 기존 확장·인증 준비와 정보의 확인 출처를 수집한다.

### Capability와 Tool Catalog

`Project + Developer + Environment → Capability → Catalog → Compatibility → Recommendation` 순서를 지킨다.
역할 하나를 특정 도구에 바로 연결하지 않는다. 예를 들어 문서 검색, API 규칙 안내, 저장소 탐색, API 테스트 같은 필요한 능력을 먼저 도출한다.

초기 Catalog는 팀이 검증한 약 **15~20개 도구**를 대상으로 한다. 인터넷 전체를 실시간 검색해 자동 설치하는 시스템으로 확장하지 않는다.
각 항목에는 식별자·이름·종류·설명, Capability, 지원 Client·OS, 인증 필요 여부, 요구 권한, 위험도, 공식 URL, 검증 버전·시점을 둔다.
LLM이 만든 도구나 확인되지 않은 호환성을 확정 추천으로 표시하지 않는다. 후보나 호환 도구가 없으면 그 상태를 설명한다.

프로젝트 전용 Skill 생성은 원래 기획의 기능 후보다. Project·Developer Profile을 바탕으로 작업 전 확인, 구현 규칙, 작업 후 검증을 구성하며 상세 범위는 해당 Feature에서 명세화한다.

## 8. Permission, Credential, Config

권한 정책 `ALWAYS_ALLOW / ASK_EACH_TIME / DENY`와 판단 결과 `ALLOW / ASK / DENY`를 구분한다.
권한 후보에는 `project.file.read`, `project.file.write`, `github.issue.read`, `github.repo.read`, `github.repo.write`, `shell.execute`, `external_service.connect`가 있다.
이는 전체 제품의 후보이며 첫 Feature의 GitHub 로그인에 저장소 권한을 추가하는 근거가 아니다.

```text
LLM → 제한된 Tool Request → Permission Manager
→ 정책·대상·작업 검사 → 허용된 Tool Executor / Backend Connector → Resource
```

- LLM에 OS 권한이나 Token을 직접 주지 않는다. Credential은 Backend 또는 Local Environment가 관리한다.
- 사용자 문서·외부 콘텐츠의 지시는 데이터로만 취급한다. 권한 변경, Secret 조회, 도구 실행의 지시로 따르지 않는다.
- 시스템 Credential과 입력에서 식별된 Secret이 Prompt·로그·오류·Audit·생성 예시·버전 관리에 들어가지 않게 한다.
- ASK는 응답 전 실행하지 않고 DENY는 차단한다. Browser 적용과 향후 Local CLI도 검사를 우회하지 않는다.
- Config에는 실제 Secret 대신 안전한 참조나 사용자가 수행할 인증 절차를 제공한다.
- 변경 Preview에 대상 경로·내용과 확인한 기존 설정 범위의 변경 유형·Diff를 표시한다. 기존 파일을 모르면 신규 환경용 설정안과 미확인 범위를 표시한다. 기존 파일을 묵시적으로 덮어쓰지 않는다.
- 취소 시 변경하지 않는다. 승인 이후 내용이나 대상이 바뀌면 기존 승인을 재사용하지 않는다.

상태 후보는 `recommended`, `approved`, `generated`, `installed`, `configured`, `auth_required`, `connected`, `verified`, `failed`다.
고정된 성공 순서로 추정하지 말고 실제 사건·검사 근거에 따라 표시한다. 검사할 수 없으면 검증 미수행으로 남긴다.

### 보완된 제품 계약

기획서와 역할은 시작점이다. 다음 기준은 팀 공통 제품 계약이며, 상세 필드·Client 변환 규칙은 해당 Feature의 Spec·Plan·계약에 연결한다.

| 판단 대상 | 공통 기준 |
| --- | --- |
| 환경 확인 | 기획서 기반 제안 / 환경 조건 확인 / 기존 설정 확인을 구분한다. OS·Client·런타임 버전·기존 확장·인증 준비 중 결과에 영향을 주는 정보만 추가로 묻고, 사용자 진술과 실제 확인을 구분한다. |
| 기존 설정과 Preview | 제공받은 설정 범위만 비교한다. 기존 파일을 모르면 '신규 환경용 설정안 · 기존 파일 미확인'으로 표시하고 실제 CREATE/UPDATE나 Diff를 단정하지 않는다. 상위 정책을 모르면 유효 권한도 미확인이다. |
| 추천 결과 | 추천 가능 / 추가 도구 불필요 / 정보 확인 필요 / 호환 후보 없음의 네 결과를 둔다. 필요한 최소 구성을 기본값으로 하고 선택적 도구는 분리한다. 도구 수를 늘리는 것을 성공으로 삼지 않는다. |
| 권한 책임 | AgentFit 자체 작업 검사, 생성할 Client 정책, 외부 도구의 실제 실행 권한을 구분한다. 권한별 작업·대상·Client 버전·변환 규칙·테스트 범위를 기록하며 지원되지 않거나 미검증인 통제를 적용했다고 표시하지 않는다. |
| 권한 기본값 | 외부 연결·파일 쓰기·실행 가능한 구성은 사용자 선택 전 비활성이다. 선택 후 지원되는 작업의 기본은 ASK_EACH_TIME이며 ALWAYS_ALLOW는 검증된 변환이 있을 때 별도 선택한다. DENY는 필요한 구성을 제외·비활성화한다. 일상적인 내부 조회마다 별도 권한 팝업을 띄우지는 않는다. |
| Catalog와 실행 내용 | 약 15~20개 도구의 패키지·포함 컴포넌트·의존·중복·충돌을 기록한다. Plugin 속 MCP·Skill·Hook을 독립 추가 도구처럼 중복 집계하지 않는다. Hook·실행 명령은 검토된 고정 템플릿과 허용 인자만 사용하고 LLM이 새 실행 코드를 만들지 않게 한다. 초기 Custom Skill은 자연어 작업 규칙으로 한정한다. |
| 검증 범위 | Client·OS·도구 버전과 단일/조합 검증을 구분한다. 실제 검사한 지원 조합만 활성화하고 버전·구성·권한 변화 시 영향받은 검증을 무효화한다. 문서 검토나 팀의 대표 환경 검증을 사용자의 실제 연결 증거로 표시하지 않는다. |
| 승인 일치 | 입력·환경·선택·정책·설정 내용이 바뀌면 Preview와 최종 승인을 갱신한다. 선택 기능인 폴더 적용 시 대상 파일을 다시 읽어 변경을 확인하고 충돌하면 중단한다. |
| 다운로드 이후 | 적용 위치·사전 준비·인증·무해한 사용 확인·실패 복구 안내를 필수 제공한다. 사용자 적용 진술과 실제 검사 결과를 분리하고 확인 주체·범위·버전·시점을 기록한다. 파일 생성만으로 installed·connected·verified를 표시하지 않는다. |
| 최소 보관 | 후속 추천·권한·설정 이력은 선택·대상·버전·승인 지문·상태·확인 근거만 보관하고 본인 접근·프로젝트 삭제에 연동한다. 기존 설정 원본, 원문을 포함하는 병합 산출물·Diff는 서버에 요청 종료 후 남기지 않으며 재생성에 필요한 입력은 다시 받는다. 전체 파일 백업·복원을 약속하지 않는다. |

기존 설정을 받기 위해 GitHub 로그인에 저장소 권한을 추가하지 않는다. Secret을 제거한 파일 선택·붙여넣기 범위만 사용하고 처리 전에 식별한 Secret을 차단·가린다.
원문 위치 정보는 저장된 원문을 다시 여는 기능이 아니다. 사용자는 처리 종료 후 자신의 원문에서 확인하며 재분석에는 입력을 다시 제출한다.

제품 가치 검증은 초보자 8명의 기존 방법 대비 동등 과제 비교로 진행한다. AgentFit에서 최소 6/8명이 안내만으로 설정 적용·무해한 사용 확인을 끝내고 기존 방법보다 완료율이 낮지 않아야 한다.
양쪽을 완료한 최소 6쌍의 참여자별 시간 비율 중앙값이 0.8 이하인지 확인하며, 실패·포기·지원 개입을 제외하지 않는다. 승인 없는 변경·안전하지 않은 권한 확대는 0건이어야 한다.
이는 작은 탐색 평가의 진행 기준이며 시장 전체 효과의 입증이 아니다. 문서 분석 사용성 5명 평가와 목적·집계를 분리한다.

첫 흐름 구현 순서는 유지하되 과거 행동 인터뷰·공식 자료 검토·수동 반례 검토는 먼저 할 수 있다. 실행 코드·설치·실제 연동이 필요한 작업은 구현 승인을 받은 범위에서 진행한다.

## 9. Architecture와 팀 경계

5인 팀·한 학기에 맞춰 Next.js → Spring Boot → FastAPI의 확정된 서비스 경계를 사용한다.
주요 모듈은 Auth, Project, Document, AI, Capability, Tool Catalog, Recommendation, Permission, Config, Integration, Audit이다.

현재 기술 계획은 Next.js 화면, Spring Boot의 인증·비즈니스 규칙·최종 검증·PostgreSQL 저장, FastAPI의 추출·AI 분석·평가다. 문서 분석은 Solar Pro 4를 1차 평가한다. 내부 서비스 계약과 정확한 패키지·버전은 새 Plan에서 정한다.
AI Provider와 Client별 Config 생성을 경계로 분리해 이후 Adapter를 추가할 수 있게 한다.
이는 구현 예정 선택이며 설치·동작 완료를 뜻하지 않는다. 상세 버전과 변경 근거는 Plan·Research에서 관리한다.

Kubernetes, Kafka, 추가 서비스, 불필요한 Vector DB·Agent Framework를 도입하지 않는다.
기존 코드나 기술 스택이 생기면 먼저 확인하고 근거 없는 전면 교체·대규모 Refactoring을 하지 않는다.

| 초기 역할 | 주 담당 |
| --- | --- |
| Full Stack A | API·DB·인증·사용자·프로젝트, AI 연동, 배포 |
| Full Stack B | Catalog·추천 Backend·호환성·권한·Config·이력, 후속 Local CLI |
| AI Developer | 문서 분석·Profile·미확정 판단·추가 질문·Capability·추천 이유·품질 평가 |
| Frontend Developer | 온보딩·업로드·결과 수정·역할·추천·권한·Preview·상태 UI |
| Designer | 초보자 UX·추천 설명·Permission·Preview·적용 UX·사용성 검증 |

역할 배분은 초기 제안이며 팀 상황에 따라 조정할 수 있다.
Entity 후보는 원래 기획을 참고하되 현재 Feature에 필요한 것만 Plan에서 확정한다.

## 10. Spec Kit 작업 절차

먼저 저장소 구조, 기존 코드·README·manifest·테스트, Git 상태, `.specify`, 설치된 Skills와 활성 Feature를 확인한다.
기존 산출물을 덮어쓰거나 처음부터 다시 만들지 말고 필요한 단계부터 이어간다.

```text
상태 확인 → speckit-constitution → speckit-specify → speckit-clarify
→ speckit-checklist → speckit-plan → speckit-tasks → speckit-analyze
→ 구현 범위 제시·사용자 명시적 승인
→ speckit-implement → 검증 → speckit-converge
```

- 설치된 `.agents/skills/speckit-*/SKILL.md` 중 해당 단계의 지침을 읽고 공식 Workflow·템플릿·스크립트를 우선 사용한다.
- Skill 미설치, 스크립트 실패 또는 별도 대체 절차를 정직하게 기록한다. 실행하지 않은 단계를 완료로 표시하지 않는다.
- Specify는 무엇과 왜, Plan은 기술 선택과 구현 방법, Tasks는 의존성·수정 파일·검증 작업을 다룬다.
- 중요한 모호성은 기존 사용자 답변을 먼저 확인하고 남은 부분만 Clarify한다.
- Analyze는 문서 간 불일치를 검사한다. 치명적 불일치는 구현 전에 문서부터 해결한다.
- 승인 후 Tasks 순서에 따라 실제 사용 가능한 단위로 구현한다. 미완료 작업을 완료 체크하지 않는다.
- Converge에서 필수 누락 작업이 발견되면 Tasks에 반영하고 승인된 범위 내에서 구현·검증을 이어간다. 범위 확대가 필요하면 먼저 알린다.
- 새 요구사항은 Spec·Clarification과 Plan·Tasks 영향을 먼저 정리한다. 독립 Feature라면 별도 Spec을 만든다.
- 사용자 결정(2026-09-25): 기능마다 구현을 시작하기 전에 `feature/<기능명>` 브랜치를 생성한다. 기능명은 짧은 영문 소문자와 하이픈으로 표현한다(예: `feature/profile-validation`). 기존에 같은 기능 브랜치가 있으면 해당 작업을 이어간다.
- 기능별 SDD 산출물·구현·테스트를 함께 검증한 뒤 해당 기능의 변경만 커밋하고 원격 브랜치에 push한다. 기능별 push는 사용자가 승인한 기본 절차이며 매번 재승인을 요청하지 않는다. `.env`·Credential·무관한 변경은 포함하지 않는다.
- 원격 저장소가 없거나 push가 실패하면 완료로 표시하지 않고 필요한 저장소 주소·접근 문제를 알린다. 자동 merge나 force push는 수행하지 않는다. Feature Directory를 Git Branch가 실제 생성된 증거로 취급하지 않는다.
- 셸 명령은 `C:\Users\fhtkr\.codex\RTK.md`에 따라 항상 `rtk`로 시작한다. 필요하면 `rtk proxy`를 사용한다.

## 11. 검증과 완료 기준

Feature에 맞는 Build, Type Check, Lint, Unit Test, Integration Test와 Acceptance Scenario를 수행한다.
UI는 실제 사용자 흐름으로 확인하고 Mock·실제 외부 연동·미수행 검증을 구분한다.

필수 검증 범주:

- 문서: 정상 PDF·Markdown·직접 텍스트, 빈 내용·손상·잠금·부분 추출, 입력 한도, AI·JSON 구조·저장 실패, 재시도·직접 작성.
- Profile: 미확정 일관성, 편집·재접속 보존, 재분석·동시 저장 충돌, 삭제 이후 늦은 응답.
- 추천: Capability 없음, 후보 없음, OS·Client 불일치, Catalog 밖 도구 차단, 추천 근거.
- 권한: Allow·Ask·Deny와 거부 우회 방지.
- Config: 신규 생성, 기존 파일 충돌·내용 보존, 유효성, Preview·승인·산출물 일치.
- 보안·보관: 비로그인·타인 접근 차단, Secret의 Prompt·로그 유입 방지, 원문·추출문 잔존 방지, 프로젝트 연관 데이터 삭제.

첫 Feature의 정량 목표는 Spec을 따른다. 9개 이상 정답 문서의 사실 추출 정확도 90% 이상, 없는 DB·배포 정보의 미확정 유지, 대표 입력 95%의 60초 내 결과 또는 명시적 실패 안내, 초보자 5명 중 4명 이상의 독립 완료 등을 포함한다.
SC-011은 6범주별 최소 2개, 총 12개 의미 사례에서 필수 값·미확정 구분이 모두 정답과 일치해야 한다. 세 입력 유형과 확정값 대조 사례를 포함한다.
SC-012는 정상 외부 서비스 조건의 독립 정상 문서 최소 30개(유형별 10개) 중 95% 이상이 첫 요청으로 검증된 초안을 저장·표시하고 사전 필수 사실 검토를 통과해야 한다. 30개면 최소 29개 성공이다. 실패·시간 초과·재시도는 첫 요청 성공으로 세지 않고 성공/실패 지연을 따로 보고한다.
이 수치는 검증 목표이며 실제 달성 결과가 아니다. 외부 서비스·실제 사용자·운영 환경이 필요한 검증을 추정으로 통과시키지 않는다.

완료 선언은 필수 요구사항 충족, Acceptance 통과, Plan과 구조 일치, 필수 Tasks 완료, 관련 테스트 통과, Analyze의 치명적 불일치 없음, Converge의 남은 필수 작업 없음이 모두 충족될 때 한다.

보고에는 현재 Feature, Spec Kit 단계 상태, 변경 내용·파일, 테스트 결과, 실제 동작, Mock·미구현, 발견된 문제와 다음 단계를 포함한다.
