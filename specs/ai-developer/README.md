# AI Developer 작업 폴더

기준: [AI Developer PRD](../../Docs/team-prds/ai-developer/PRD.md), [첫 Feature Tasks](../../specs/001-project-document-analysis/tasks.md).

현재 결정과 평가 절차: [Solar Pro 4 Provider 평가](provider-evaluation.md).

2026-09-25 확인된 Spring Boot → FastAPI 서비스 분리와 미합의 내부 계약은 [FastAPI 서비스 경계·계약 초안](fastapi-service-contract.md)에 기록했다. 기존 첫 Feature Plan·Tasks의 단일 Next.js 서버 구조는 재작성 전까지 구현 기준으로 사용하지 않는다.

AI 파트의 새 작업 순서는 [FastAPI 구현 계획](fastapi-implementation-plan.md)과 [AI Developer Tasks](tasks.md)에 정리했다. 실패 건에서 수신한 LLM 원본 응답은 오류 추적용으로 최대 7일 보관한다.

이 폴더는 기능별 조사·설계·평가 자료를 정리하는 공간이다. 애플리케이션 구현 파일은 승인된 작업 범위에 따라 첫 Feature Tasks의 `src/`, `tests/`, `scripts/` 위치에 작성한다.

기능별 구현은 사용자 요청에 따라 Spec → Plan → Tasks → 테스트 → 구현 → 검증의 SDD 순서로 진행한다. 첫 적용은 [Profile 후보 검증 Spec](01-profile-contract/spec.md)·[Plan](01-profile-contract/plan.md)·[Tasks](01-profile-contract/tasks.md)다. 현재 구현은 `ai_service/`의 순수 검증 모듈이며, 아래 기존 `src/` 경로 설명은 단일 Next.js 서버 계획의 이전 기준이다.

## 1단계: 문서 분석

1. [profile-contract](01-profile-contract/README.md): Profile 필드·출처·미정·근거·오류 계약
2. [evaluation-fixtures](02-evaluation-fixtures/README.md): 사전 정답과 합성 평가 사례
3. [document-extraction](03-document-extraction/README.md): PDF·Markdown·텍스트 추출
4. [analysis-provider](04-analysis-provider/README.md): Provider·Prompt·구조화 출력
5. [evidence-validation](05-evidence-validation/README.md): 근거와 문맥 의미 검증
6. [failure-security](06-failure-security/README.md): 실패 분류·Secret·지시 주입·보관 경계
7. [quality-evaluation](07-quality-evaluation/README.md): 정확도·성공률·지연 평가

## 후속 단계

8. [capability-analysis](08-capability-analysis/README.md): 역할·환경 기반 Capability
9. [recommendation-explanation](09-recommendation-explanation/README.md): 검증 후보의 추천 근거·설명
10. [custom-skill-content](10-custom-skill-content/README.md): 자연어 Project Skill 내용
