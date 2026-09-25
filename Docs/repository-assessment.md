# AgentFit 인수인계 초기 점검

점검일: 2026-09-07 (Asia/Seoul)

> 후속 상태 (2026-09-07): 사용자가 Spec Kit을 설치했다. `.specify`와 프로젝트의 Spec Kit Skills 10개를 확인했으며, 설치 메타데이터는 `1.0.5.dev0`이다. [Constitution v1.0.0](../.specify/memory/constitution.md)을 작성하고 [Project Document Analysis 명세](../specs/001-project-document-analysis/spec.md)를 시작했다. 아래 내용은 **설치 전 최초 점검 기록**이며, 현재 요구사항과 결정은 Constitution 및 Feature Spec을 따른다. Git 저장소와 Application Code는 후속 확인 시에도 없었다.

## 현재 Feature

PHASE 0 — Repository / Spec Kit 상태 확인.

다음 Feature는 인수인계 문서의 STEP 7을 따라 **Project Document Analysis**로 잡는다. 프로젝트 생성 → PDF/MD 업로드 → 텍스트 추출 → LLM 분석 → 구조화된 Project Profile 저장 → 결과 확인·수정 → 재저장 흐름을 우선한다. 현재 기반 코드가 없으므로 Project Foundation의 최소 프로젝트 생성·목록·상세·저장 기능을 선행 의존성으로 명세에 반영해야 한다. 기능 분할과 구현 순서는 Spec Kit 산출물에서 확정한다.

## 확인된 현재 상태

점검 시작 시 `E:\AgentFit`에는 빈 `Docs` 폴더만 있었다.

| 항목 | 확인 결과 |
| --- | --- |
| Framework | 코드와 manifest가 없어 미선정 |
| Package Manager | 프로젝트 manifest와 lockfile 없음. 시스템 명령 존재는 프로젝트 선택의 근거가 아님 |
| DB / ORM | 설정·schema·migration 없음 |
| 기존 코드 | 없음 |
| 테스트 / CI | 없음 |
| README | 없음 |
| Git | `git status --short --branch` 결과 `Not a git repository` |
| Spec Kit 초기화 | `.specify` 없음 |
| Spec Kit Skills | 현재 세션 목록 및 접근 가능한 프로젝트·사용자 Skills·플러그인 캐시에서 찾지 못함 |
| Specify CLI | `C:\Users\fhtkr\.local\bin\specify.exe` 존재. 권한 확장 실행에서 `specify init --help` 성공 |

확인한 Skills 위치: 프로젝트, `C:\Users\fhtkr\.agents\skills`, `C:\Users\fhtkr\.codex\skills`, `C:\Users\fhtkr\.codex\plugins\cache`, `C:\Users\fhtkr\.claude`. `C:\Users\fhtkr\.config` 검색은 접근 거부로 확인하지 못했다. 전역 어디에도 없다고 단정하지 않으며, 현재 사용할 수 있는 Spec Kit Skill은 확인되지 않았다.

일반 샌드박스에서 `specify`는 `uv trampoline failed to canonicalize script path` 오류가 났고, `uv tool list`도 전역 캐시 접근에 실패했다. 권한을 확장한 **도움말 조회만** 성공했으므로 CLI 설치 손상으로 판단하지 않는다. CLI 재설치나 초기화는 실행하지 않았다.

프로젝트 지침으로 지정된 `C:\Users\fhtkr\.codex\RTK.md`를 확인했으며, 확인 이후 셸 명령에 `rtk`를 사용했다. `rtk rg`의 환경 조회 오류 때문에 파일 검색은 `rtk proxy rg`로 수행했다.

## AgentFit 요구사항과의 Gap

| 영역 | 필요한 상태 | 현재 Gap / 다음 처리 |
| --- | --- | --- |
| 개발 기준 | Constitution → Spec → Clarification → Plan → Tasks → 구현 | 모든 산출물이 없어 공식 초기화부터 필요 |
| 첫 사용자 흐름 | 프로젝트 생성과 문서 분석·확인·수정·저장 | 전체 미구현. 첫 Feature에서 우선 처리 |
| 불확실성 처리 | 근거 없는 필드는 null / unknown, 사용자 수정 가능 | 명세와 acceptance scenario에 반영 필요 |
| 문서 처리 | PDF, Markdown, 직접 텍스트 입력 요구 | PDF/MD는 명시됨. 직접 입력의 첫 Feature 포함 여부, 파일 크기·페이지 수·암호화 PDF·실패 UX 결정 필요 |
| 접근과 개인정보 | 로그인 여부·접근 범위·보관 정책 | 로그인 흐름은 제시됐으나 첫 Feature 인증 범위와 원문 보관 정책 미확정 |
| 추천 | Profile → Capability → 검증된 Catalog → 호환성 검사 → 추천 | 미구현. 첫 문서 분석 흐름 완료 이후 진행 |
| 권한과 Secret | Permission Manager 경유, Secret과 LLM 분리 | 미구현. 헌법과 향후 관련 명세에 필수 제약으로 기록 |
| 설정 생성 | Preview → 승인 → 생성·다운로드, 상태 증거 구분 | 미구현. Claude Code 우선, 기존 파일 충돌과 설정 범위는 추측하지 않음 |
| 검증 | 필수 요구사항·acceptance·테스트·analyze·converge 충족 | 테스트 기반 없음. Plan과 Tasks에서 검증 전략 결정 |

기술 스택은 아직 확정하지 않는다. 인수인계 문서의 Next.js / TypeScript / PostgreSQL / Prisma / Zod / OpenAI API는 후보이며, Technical Plan에서 결정한다. Architecture는 소규모 팀에 맞는 Modular Monolith를 우선 검토한다.

## 공식 초기화 제안 — 미실행

설치된 CLI의 도움말과 [GitHub Spec Kit 공식 초기화 구현](https://github.com/github/spec-kit/blob/main/src/specify_cli/commands/init.py)에서 Codex Skills 옵션을 확인했다.

실행 위치: `E:\AgentFit`

```powershell
rtk proxy specify init --here --integration codex --integration-options="--skills" --script ps --non-interactive --force
```

예상 산출물은 `.specify`의 템플릿·스크립트·워크플로와 `.agents/skills`의 Spec Kit Skills다. 세부 생성 파일과 Git 초기화 여부는 실행 결과를 확인해야 한다. `--force`는 기존 폴더 병합·덮어쓰기 확인을 생략하는 옵션이므로 실제 실행 직전에 현재 파일 상태와 생성 경로의 충돌을 다시 확인해야 한다.

이 명령의 `codex`는 **AgentFit을 개발하는 에이전트용 통합**을 뜻한다. AgentFit MVP가 지원하는 클라이언트는 인수인계 요구대로 **Claude Code 우선**이다.

인수인계의 PHASE 0은 미초기화 상태에서 공식 초기화를 제안하도록 지시한다. 현재 Spec Kit Skills가 확인되지 않았으므로, 초기화와 Constitution 생성은 수행했다고 보고하지 않는다.

## Constitution에 반영할 요구사항 — 아직 Constitution 산출물 아님

1. Beginner First: 초보자가 이해할 수 있는 설명과 수정 가능한 결과를 제공한다.
2. Explicit Permission: 실제 작업은 사용자 정책과 승인 범위 안에서만 실행한다.
3. LLM Is Not Authority / Output Verification: LLM은 근거 없는 사실과 권한을 확정하지 않으며, 출력은 검증한다.
4. Verified Tool Catalog: 검증된 Catalog와 호환성 검사를 통과한 도구만 확정 추천한다.
5. Secret Isolation: API Key, Token, Password, Private Key를 LLM Context에 전달하지 않는다.
6. Preview Before Mutation: 프로젝트 설정 변경 전에 대상과 내용·Diff를 보여주고 승인받는다.
7. Auditability: 중요한 승인·생성·적용·실패를 Secret 없이 추적한다.
8. Minimal MVP: 한 학기·5인 팀 범위를 지키고 문서 분석부터 단계별 사용자 흐름을 완성한다.
9. Testable Requirements / Recommendation: 요구사항과 추천 경로를 재현 가능한 acceptance scenario와 테스트로 검증한다.
10. Config Generation != Verification: 파일 생성만으로 설치·연결·작동 검증 완료를 표시하지 않는다.

## Spec Kit 상태

| 단계 | 상태 |
| --- | --- |
| Repository 점검 | 완료, 일부 전역 경로 접근 제한은 위에 기록 |
| 공식 초기화 | 제안 준비, 미실행 |
| Constitution | 미시작 — 필요한 Skills 미확인 |
| Specify / Clarify / Checklist | 미시작 |
| Plan / Tasks / Analyze | 미시작 |
| Implement / Converge | 미시작 |

## 이번 변경 및 검증

- 변경 파일: `Docs/repository-assessment.md` (이 보고서만 추가).
- 기존 Application Code 변경: 없음.
- 수행 확인: 디렉터리·파일 검색, Git 상태, 도구 경로, Skills 탐색, Specify 초기화 도움말 조회.
- Build / Type Check / Lint / Unit / Integration / Acceptance: 실행 대상 프로젝트가 없어 수행하지 않음. 통과로 기록하지 않음.
- 현재 실제 동작하는 AgentFit 기능: 없음.
- Mock: 없음. Application 전체 미구현.

## 다음 단계

1. 공식 초기화 제안을 확정하고 실행한다.
2. 실제 생성된 Spec Kit Skills를 읽고 constitution Skill부터 사용한다.
3. Constitution 결과를 사용자에게 보여준다.
4. Project Document Analysis의 specify → clarify → checklist → plan → tasks → analyze를 수행한다.
5. 파일 크기, AI 실패 UX, 로그인 범위 등 추측 금지 사항을 Clarification에서 해소한다.
6. 산출물 간 일관성이 확인된 후 implement → validation → converge로 진행한다.

참고: [Spec Kit 공식 Quick Start](https://github.github.com/spec-kit/quickstart.html), [공식 CLI Reference](https://github.github.com/spec-kit/reference/core.html).
