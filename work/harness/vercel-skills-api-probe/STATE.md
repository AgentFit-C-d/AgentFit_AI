# 작업 상태

## 목표
- Vercel Preview에서 skills.sh OIDC 인증·검색을 시험한다. Full Stack·기존 AI 모듈은 변경하지 않는다.
- 승인된 방식은 Speckit 문서와 TDD Red–Green이다.

## 현재 상태
- `feature/vercel-skills-api-probe`의 독립 worktree에 시험 함수·테스트·명세를 작성했다.
- 로컬 검증: Node 테스트 9개 통과, `node --check` 성공. 현재 기준인 `origin/main`의 AI 테스트는 0개 수집되어 실행되지 않았다.
- 실제 Vercel 프로젝트 연결·Preview 배포·skills.sh 호출은 미실행이다. Vercel CLI가 PATH에 없고 프로젝트 접근·OIDC 설정이 확인되지 않았다.

## 결정 및 제약
- 프로브는 결과 `id`·`name`만 반환하고 검증 Catalog 또는 최종 추천으로 승격하지 않는다.
- `PROBE_KEY`와 Vercel OIDC 토큰은 런타임에만 사용한다. `.env*`와 `.vercel/`은 프로젝트 `.gitignore`에서 제외한다.
- 저장소의 기존 다른 변경과 이 기능을 섞지 않는다. 기본 worktree 도구는 Git 소유권 검사에 실패해, 기존 `tmp/` ignore 경로에 수동 worktree를 만들었다.
- worktree는 처음에 이전 기능 HEAD에서 출발했으나 커밋 전 `origin/main`으로 재설정했다. 스테이징된 신규 프로브 파일만 남았다.

## 다음 단계
- 스테이징된 diff·비밀 파일·테스트를 최종 점검한다.
- 배포 전 구체적인 영향과 검증 결과를 사용자에게 제시하고 확인받는다. 실제 호출 뒤 `specs/003-vercel-skills-api-probe/validation.md`에 상태·시각·후보 수를 기록한다.
