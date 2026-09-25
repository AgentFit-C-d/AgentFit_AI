# AI Developer Tasks — FastAPI

**상태:** 2026-09-25 계획. 체크된 구현 작업 없음. 내부 계약의 미정 필드·원본 응답 보관 방식은 Full Stack A와 합의 후 고정한다. 기존 [첫 Feature Tasks](../001-project-document-analysis/tasks.md)의 단일 Next.js 서버 파일 경로는 사용하지 않는다.

## 1. 계약·평가 준비

- [ ] AD001 Full Stack A와 FastAPI 내부 요청/응답·서비스 인증·오류 코드·timeout/취소·멱등성·진단 응답 전달 계약을 확정하고 예시·검증 사례를 기록한다. [01](01-profile-contract/README.md)
- [ ] AD002 Profile 10개 필드·출처·미정·근거 위치 schema와 Spring Boot의 최종 검증 항목을 맞춘다. [01](01-profile-contract/README.md)
- [ ] AD003 FACT 9개, SEM 12개, NORMAL 30개와 ERROR 합성 문서·사전 정답을 고정한다. [02](02-evaluation-fixtures/README.md)
- [ ] AD004 Solar Pro 4의 인증·구조화 출력·오류·데이터 처리 조건을 확인하고 합성 입력으로 첫 평가를 기록한다. 최종 모델 채택은 평가 후 결정한다. [Provider 평가](provider-evaluation.md)

## 2. FastAPI 분석 서비스

- [ ] AD005 FastAPI 서비스 골격과 내부 인증·입력 제한·요청 식별자·안전한 응답 경계를 구현한다. 공개 사용자 인증/DB 연결은 두지 않는다. (AD001 선행)
- [ ] AD006 PDF·Markdown·직접 텍스트 추출과 10 MiB/100쪽/100,000 code-point 경계, 손상·잠금·부분 추출, 취소·timeout 처리를 구현한다. [03](03-document-extraction/README.md)
- [ ] AD007 Provider Adapter·Prompt·구조화 출력·거절/불완전 응답·안전 오류 변환을 구현한다. (AD004 선행) [04](04-analysis-provider/README.md)
- [ ] AD008 값·출처·미정·근거 위치 및 의미 반례를 검증하고 실패 시 검증된 초안을 반환하지 않는다. [05](05-evidence-validation/README.md)
- [ ] AD009 실패 건에서 실제 수신한 LLM 원본 응답만 진단 경로로 전달한다. 정상 응답·일반 로그·Audit·평가 파일에 원본을 남기지 않는다. 7일 만료·프로젝트 삭제 검증은 Spring Boot와 함께 수행한다. [06](06-failure-security/README.md)

## 3. 검증·인계

- [ ] AD010 입력 경계·추출 실패·Provider/구조/근거 오류·Secret/문서 지시·취소/timeout 단위 및 계약 테스트를 실행한다.
- [ ] AD011 Spring Boot 연동에서 AI 성공 → 최종 검증 → DB 저장 → 공개 성공 순서와 저장 실패·지연 응답·기존 확인 Profile 보존을 확인한다. FastAPI 단독 성공을 저장 성공으로 세지 않는다.
- [ ] AD012 사전 정답 평가와 실제 Provider·DB·화면 전체 흐름 결과를 구분해 기록한다. FACT/SEM/NORMAL/ERROR와 지연·실패 분모를 유지한다. [07](07-quality-evaluation/README.md)

**선행 관계:** AD001–AD004 → AD005–AD009 → AD010–AD012. AD003과 AD001은 독립적으로 진행할 수 있다. AD011–AD012에는 Full Stack A·Frontend의 실제 연결이 필요하다.
