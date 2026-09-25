# Quickstart and Validation Guide

이 문서는 구현 후 실행할 절차다. 명령이 아직 구현되지 않았거나 검증되지 않은 상태를 완료로 간주하지 않는다.
데이터 구조는 [data-model.md](data-model.md), 인터페이스는 [contracts/http.md](contracts/http.md)를 따른다.

2026-09-25 현재 Solar Pro 4가 [문서 분석 1차 평가 모델](../ai-developer/provider-evaluation.md)이다. 아래 `OPENAI_API_KEY`·`OPENAI_MODEL`은 이전 OpenAI 구현 기준안의 값이며 현재 Solar 평가용 요구사항이 아니다. 평가 결과로 Provider를 선정한 뒤 서버 변수·API 호출·보관 안내를 갱신하고 실행한다.
초기 평가는 로컬에서 수행한다. Solar 시험용 `UPSTAGE_API_KEY`는 로컬 실행 프로세스에만 전달하며, 키 파일을 사용할 경우 먼저 Git 제외 규칙을 갖춘다. 배포 단계의 서버 `.env` 설정은 이후 작업이다. 호출 예산 상한은 없지만 시험 표본·호출 횟수·비용을 기록한다.

## Prerequisites

- Node 24 LTS 권장. 로컬 Node 22.16.0도 현재 선택된 dependency engine 범위를 충족한다.
- npm, 실행 중 Docker 또는 별도로 제공된 PostgreSQL 17.
- GitHub OAuth App: callback `http://localhost:3000/api/auth/callback/github`.
- 서버 환경: DATABASE_URL, BETTER_AUTH_URL, BETTER_AUTH_SECRET, GITHUB_CLIENT_ID,
  GITHUB_CLIENT_SECRET, OPENAI_API_KEY, OPENAI_MODEL.
- 값을 채팅·로그에 출력하지 않고 `.env.example`을 참고해 gitignore 대상 `.env`에 설정한다.
  예시 파일은 값 없는 자리표시자만 포함한다. 사용자 기존 Credential을 읽어 재사용하지 않는다.

## Local Setup (구현 예정 명령)

```powershell
rtk proxy npm.cmd ci --cache E:\AgentFit\.cache\npm
rtk proxy docker compose up -d db
rtk proxy npm.cmd run db:generate
rtk proxy npm.cmd run db:migrate
rtk proxy npm.cmd run dev
```

의도한 빈 개발 DB에만 migration을 적용한다. 기존 데이터가 있는 외부 DB를 reset하지 않는다.
Docker 미실행 또는 Credential 미설정 시 그 준비 상태를 안내하고 인증 우회나 가짜 AI 성공을 활성화하지 않는다.

## Automated Validation (구현 예정 명령)

```powershell
rtk proxy npm.cmd run typecheck
rtk proxy npm.cmd run lint
rtk proxy npm.cmd run test
rtk proxy npm.cmd run test:integration
rtk proxy npm.cmd run build
rtk proxy npm.cmd run test:e2e
```

- Unit: 입력 바이트·code-point·페이지 경계, Secret 검사, 근거 대조·unknown 재계산,
  provider 거절·잘못된 구조·timeout·원문 미보관.
- 실제 PDF: 텍스트 PDF, Markdown, 빈·손상·잠금·부분 추출 문서, 100/101쪽.
- Integration: 독립 테스트 PostgreSQL에서 세션·소유권·version 충돌·cascade·늦은 결과·Audit·Secret 미보관 검증.
  테스트 DB임을 검증한 후 fixture만 정리한다. 운영 DB URL을 테스트에 사용하지 않는다.
- E2E: 로컬 UI의 정상·오류·수정 보존·키보드·로그아웃을 검증한다.
  테스트 전용 세션 fixture는 테스트 서버에서만 사용하며 production 인증 우회 경로를 만들지 않는다.

## Actual Service Acceptance

1. GitHub로 로그인하고 프로젝트를 생성한다. 로그아웃·재로그인 후 같은 프로젝트가 보이는지 확인한다.
2. 다른 GitHub 사용자로 해당 프로젝트 접근을 시도해 내용·존재 여부가 노출되지 않는지 확인한다.
3. 정상 PDF·Markdown·직접 텍스트를 실제 AI로 분석하고 DB·배포 미기재 항목이 미정인지 확인한다.
4. 결과를 수정·저장하고 새로고침한다. 재분석이 확인된 값을 덮어쓰지 않는지 확인한다.
5. AI 오류에서 재입력·직접 작성·저장을 각각 확인한다. 오류를 AI 성공으로 표시하지 않는다.
6. 삭제 확인·취소·완료와 지연 분석 결과가 삭제 데이터를 복원하지 않는지 확인한다.
7. 사전 고정 FACT 최소 9개·SEM 12개·NORMAL 30개 fixture로 `npm run eval:analysis`를 실행해 SC-003 정확도, SC-011 의미 정답, SC-012 첫 요청 저장·표시·필수 사실 성공률과 SC-008 지연을 기록한다. NORMAL은 30개 중 최소 29개가 첫 요청에 성공해야 하며 성공/실패 지연·전체 분모·재시도를 구분한다.
   이 명령은 실제 API를 사용하므로 횟수·입력 범위를 명시하고 합성 문서만 사용한다.
8. 개발 초보자 5명의 진행자 개입 없는 사용성 평가로 SC-007을 기록한다.

## Retention and Crash Validation

합성 canary를 포함한 문서로 성공·실패·timeout·프로세스 종료를 재현한 후
DB·앱 로그·관리하는 임시 파일·캐시에서 원문/추출문이 저장되지 않았는지 확인한다.
배포 시 proxy body spooling·APM·swap·core/heap dump 설정도 검증한다.
메모리의 물리적 즉시 소거 또는 OpenAI의 Zero Data Retention을 보장했다고 기록하지 않는다.

## Completion Record

각 검사에 실행 명령, 실제 결과, 환경, Mock 여부와 미수행 사유를 남긴다.
실제 OAuth/AI, p95, 사용성, 배포 보관 조건 중 필수 검증이 남으면 Feature 완료로 표시하지 않는다.
