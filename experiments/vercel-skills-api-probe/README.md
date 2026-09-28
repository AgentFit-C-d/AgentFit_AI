# skills.sh Vercel 인증 프로브

이 디렉터리는 skills.sh API가 Vercel 프로젝트의 OIDC 토큰을 받아들이는지 확인하는 독립 시험용이다. AgentFit 추천 서비스에 연결되지 않으며 검색 결과를 검증된 Catalog로 취급하지 않는다.

## 로컬 검증

Node.js 22에서 이 디렉터리를 작업 디렉터리로 지정한다.

```powershell
npm ci
npm test
node --check api/search.js
```

자동화 테스트는 토큰·외부 응답을 시험용 함수로 대체한다. 따라서 통과해도 실제 skills.sh 인증이 확인된 것은 아니다.

## Vercel Preview 실호출

1. Vercel 계정의 별도 시험 프로젝트에 **이 디렉터리만** 연결한다. 저장소 전체를 프로젝트 루트로 배포하지 않는다. Vercel CLI가 없다면 공식 CLI를 설치하거나 `npx vercel`을 사용한다.
2. Vercel 프로젝트의 **Settings → OIDC Federation**을 켠다. [skills.sh API 인증 안내](https://www.skills.sh/docs/api)에 따라 함수가 요청 시점의 OIDC 토큰을 가져온다.
3. Vercel의 **Preview 환경 변수** `PROBE_KEY`에 임의의 긴 시험 비밀을 등록한다. 비밀 값을 `.env`, 문서, CLI 인자, 커밋에 넣지 않는다. `vercel env add PROBE_KEY preview`의 대화형 입력을 이용할 수 있다.
4. Preview에 배포한 다음 `GET /api/search?q=react%20native&limit=2`를 호출한다. 요청 헤더 `x-probe-key`에 같은 비밀을 보낸다. 응답은 `status`, `query`, `count`, `data`의 후보 `id`·`name`만 포함한다.
5. 헤더 없이 같은 경로를 호출하면 `401 UNAUTHORIZED`가 나오는지 확인한다. 실호출 결과는 시각·HTTP 상태·후보 수만 `specs/003-vercel-skills-api-probe/validation.md`에 기록한다.

함수는 검색어 2~80자와 결과 1~10개만 허용한다. 검색당 외부 API 호출은 최대 한 번이며, 응답을 캐시하지 않는다. `OIDC_UNAVAILABLE`은 Vercel 프로젝트의 OIDC 설정을, `UPSTREAM_AUTH_FAILED`는 skills.sh의 토큰 수락 여부를 확인해야 한다는 뜻이다. 외부 오류의 본문이나 토큰은 응답에 포함하지 않는다.

이 프로브는 운영용 인증·추천 API가 아니다. 시험 뒤에는 Preview 배포와 `PROBE_KEY`를 프로젝트에서 정리한다.
