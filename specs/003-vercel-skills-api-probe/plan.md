# Implementation Plan: Vercel skills.sh 인증 시험

**Branch**: `feature/vercel-skills-api-probe` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

저장소의 독립된 시험 디렉터리에 Vercel Node.js 함수 하나를 둔다. 함수는 시험용 접근 비밀을 확인한 후 요청마다 Vercel OIDC 토큰을 받아 skills.sh 검색 API를 호출한다. 반환 필드는 상태와 제한된 후보 식별 정보뿐이다. 배포 및 실제 호출은 별도로 구분해 검증한다.

## Technical Context

**Language/Version**: Vercel 지원 Node.js 런타임의 JavaScript
**Primary Dependencies**: `@vercel/oidc`; 테스트는 Node.js 내장 test runner
**Storage**: 없음
**Testing**: 토큰 공급·HTTP 호출을 주입한 자동화 테스트와 실제 Vercel 시험 호출
**Target Platform**: 독립 Vercel 시험 프로젝트의 Preview 환경
**Project Type**: 일회성 외부 API 인증 프로브
**Performance Goals**: 요청당 검색 API 1회, 결과 상한 10개
**Constraints**: Full Stack 및 AI 모듈 변경 없음, 비밀 값 비노출, 운영 추천 경로 비연결
**Scale/Scope**: 개발자 시험 호출 한정

## Constitution Check

- 외부 검색 결과를 검증 Catalog 또는 추천으로 승격하지 않는다.
- 비밀 값은 런타임 환경에만 둔다. 오류 본문과 토큰을 사용자 응답이나 로그에 포함하지 않는다.
- 추가 Vercel 함수는 AgentFit 운영 서비스가 아닌 임시 인증 실험이다. 운영 아키텍처 변경이 필요해지면 별도 명세와 승인을 받는다.
- Full Stack 코드 및 기존 Next.js → Spring Boot → FastAPI 경계는 변경하지 않는다.

## Project Structure

```text
specs/003-vercel-skills-api-probe/
  spec.md
  plan.md
  tasks.md
  research.md
  quickstart.md

experiments/vercel-skills-api-probe/
  api/search.js
  package.json
  test/search.test.js
  README.md
  .gitignore
```

## Design

1. 별도 디렉터리를 Vercel 프로젝트 루트로 연결한다. 저장소 루트나 Full Stack 앱을 배포 대상으로 삼지 않는다.
2. 프로브는 접근 비밀과 입력 한도를 먼저 확인한다. 권한 없는 요청은 토큰 발급과 외부 호출 전에 종료한다.
3. Vercel 함수 요청 안에서 `getVercelOidcToken()`을 호출하고 검색 API에 `Authorization: Bearer`로 전달한다.
4. 응답은 성공 여부, 검색어, 후보 수 및 최대 10개의 `id`·`name`만 포함한다. 실패는 자체 코드로 정규화한다.
5. 로컬 모의 테스트를 Red–Green으로 진행한다. Vercel 프로젝트 연결·OIDC 활성화·Preview 배포 뒤 실제 호출로 인증 가능성을 확인한다.

## Alternatives Considered

- Vercel CLI의 로컬 토큰으로만 시험: 빠르지만 배포 런타임의 OIDC 동작을 확인하지 못한다.
- 기존 AI 서비스에 프록시 엔드포인트 추가: 팀 경계를 바꾸고 이번 시험 목적을 초과한다.

## External Prerequisites

- Vercel 계정·시험 프로젝트 접근, OIDC Federation 활성화, Preview 환경의 시험 접근 비밀.
- 실제 프로젝트 생성·배포에는 별도 외부 영향과 비용을 확인한다. 준비가 안 되면 로컬 테스트 결과만 보고한다.
