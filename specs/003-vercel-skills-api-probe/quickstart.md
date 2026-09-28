# 검증 Quickstart (구현 승인 후)

1. `experiments/vercel-skills-api-probe/`에서 `npm ci`, `npm test`, `node --check api/search.js`를 실행해 Red–Green 및 오류 경계를 확인한다.
2. 해당 디렉터리만 Vercel 시험 프로젝트에 연결하고 OIDC Federation을 켠다. 시험 접근 비밀은 Vercel Preview 환경 변수에 설정하며 저장소 파일에 쓰지 않는다.
3. Preview 배포 URL의 `GET /api/search?q=react%20native&limit=2`에 `x-probe-key` 헤더를 넣어 한 번 실행한다. 응답 상태·시각·후보 수만 기록하고 토큰이나 비밀 값은 기록하지 않는다.
4. 접근 비밀 없는 호출이 외부 API를 호출하지 않고 거부되는지 확인한다.

실제 프로젝트 연결·배포가 이뤄지지 않으면 외부 연동 검증은 미수행으로 기록한다.
