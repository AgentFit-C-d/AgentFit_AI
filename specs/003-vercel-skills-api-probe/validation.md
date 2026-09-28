# 검증 기록

## 구현 범위

- 독립 Node.js Vercel 함수와 자동화 테스트를 작성했다. 기존 Full Stack 및 AI 모듈은 수정하지 않았다.
- 검색은 요청당 최대 1회, 검색어 2~80자, 결과 상한 10개로 제한한다.
- 외부 결과는 시험 데이터이며 검증 Catalog·최종 추천으로 사용하지 않는다.

## Red–Green

- US1 Red: `api/search.js`가 없는 상태에서 `npm test`가 `ERR_MODULE_NOT_FOUND`로 실패했다. 이후 최소 검색 함수를 작성해 3개 테스트가 통과했다.
- US2 Red: 접근 거부·설정 누락·잘못된 입력·외부 401/429/503·비정상 응답 사례에서 5개 테스트가 실패했다. GET 전용 테스트도 외부 호출 시도로 실패했다. 접근 검사와 오류 매핑 구현 후 전체 9개 테스트가 통과했다.

## 실행 결과 (2026-09-28)

| 확인 | 결과 |
| --- | --- |
| `npm ci --no-audit --no-fund` | 성공, 24개 패키지 설치 |
| `npm test` | 9개 통과, 실패 0개 |
| `node --check api/search.js` | 성공 |
| `npm ls --depth=0` | `@vercel/oidc@3.8.9` 설치 확인 |
| `py -3.12 -m unittest discover -s tests -q` (`ai_service/`) | 현재 기준인 `origin/main`에는 실행할 AI 테스트가 없어 0개 수집, 종료 코드 1. 이전 기능 커밋 기준 작업 공간에서는 372개가 통과했으나 이 기능 브랜치의 검증 결과로 간주하지 않음 |
| Vercel CLI | `npx vercel` 60.1.3으로 프로젝트 연결 및 Preview 배포 성공 |
| 첫 Preview 무인증 요청 | 2026-09-28 08:20:17 UTC · HTTP 503 · 후보 수 해당 없음 |
| Vercel Preview 무인증 요청 | 2026-09-28 08:26:24 UTC · HTTP 401 · 후보 수 해당 없음 |
| Vercel Preview skills.sh 실호출 | 2026-09-28 08:29:28 UTC · HTTP 200 · 후보 수 2 |

SC-001의 실제 OIDC 인증 및 검색 성공을 Preview 실호출로 확인했다. 자동화 테스트는 외부 HTTP와 토큰을 시험 함수로 대체한다.
