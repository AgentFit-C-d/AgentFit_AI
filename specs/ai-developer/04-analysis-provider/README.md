# 분석 Provider

- Provider 인터페이스, Prompt, 구조화 출력과 거절·시간 초과·오류 계약을 다룬다.
- 문서에 없는 기술을 채우지 않고 검증 가능한 Profile 초안을 반환한다.
- FastAPI 안에서 Provider 호출·구조화 출력·근거 검증을 수행하고 Spring Boot에는 검증된 초안 후보 또는 안전한 오류를 반환한다. [서비스 경계 초안](../fastapi-service-contract.md)을 따른다.
- 기존 T018, T021과 `src/modules/analysis/` 경로는 단일 Next.js 서버 계획의 항목이므로 새 Plan·Tasks에서 재배정한다.
