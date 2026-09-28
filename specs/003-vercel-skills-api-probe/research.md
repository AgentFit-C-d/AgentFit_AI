# Research: Vercel skills.sh 인증 시험

- **Decision**: Vercel 프로젝트의 요청별 OIDC 토큰을 사용한다. skills.sh 공식 API 문서는 이 인증 방식을 안내하며 검색 엔드포인트를 제공한다. [skills.sh API](https://www.skills.sh/docs/api)
- **Decision**: 프레임워크 없는 독립 Node.js 함수를 사용한다. Vercel은 프로젝트 루트의 `api/` 파일을 함수로 제공한다. [Vercel Node.js Runtime](https://vercel.com/docs/functions/runtimes/node-js)
- **Decision**: 이 함수는 시험용이며 기존 Python `SkillsShClient`를 복제·통합하지 않는다. 목적은 실인증 가능성 확인이다.
- **Alternative**: 로컬 Vercel CLI 연동만으로도 토큰 시험은 가능하지만, Preview 런타임에서의 동작을 입증하지 못한다.
