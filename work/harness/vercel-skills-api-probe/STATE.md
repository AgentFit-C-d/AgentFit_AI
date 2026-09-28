# 작업 상태

## 목표
- Vercel Preview에서 skills.sh OIDC 인증·검색을 시험한다. Full Stack·기존 AI 모듈은 변경하지 않는다.
- 승인된 방식은 Speckit 문서와 TDD Red–Green이다.

## 현재 상태
- `feature/vercel-skills-api-probe`의 독립 worktree에 시험 함수·테스트·명세를 작성했다.
- 로컬 검증: Node 테스트 9개 통과, `node --check` 성공. 현재 기준인 `origin/main`의 AI 테스트는 0개 수집되어 실행되지 않았다.
- `npx vercel` 60.1.3으로 Vercel 프로젝트를 연결하고 Preview 배포를 완료했다. 첫 Preview 요청은 08:20:17 UTC HTTP 503이었다. 재배포 뒤 08:26:24 UTC 무인증 요청은 HTTP 401, 08:29:28 UTC 인증된 skills.sh 검색은 HTTP 200·후보 2건이었다.

## 결정 및 제약
- 프로브는 결과 `id`·`name`만 반환하고 검증 Catalog 또는 최종 추천으로 승격하지 않는다.
- `PROBE_KEY`와 Vercel OIDC 토큰은 런타임에만 사용한다. `.env*`와 `.vercel/`은 프로젝트 `.gitignore`에서 제외한다.
- 저장소의 기존 다른 변경과 이 기능을 섞지 않는다. 기본 worktree 도구는 Git 소유권 검사에 실패해, 기존 `tmp/` ignore 경로에 수동 worktree를 만들었다.
- worktree는 처음에 이전 기능 HEAD에서 출발했으나 커밋 전 `origin/main`으로 재설정했다. 스테이징된 신규 프로브 파일만 남았다.

## 다음 단계
- 검증 기록과 Vercel CLI가 추가한 `.gitignore`를 점검해 기능 브랜치에 반영한다.
- 시험이 끝난 뒤 Preview 배포와 `PROBE_KEY` 정리 여부를 사용자와 결정한다.
