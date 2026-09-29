# AI Developer 작업 폴더

기준: [AI Developer PRD](../../Docs/team-prds/ai-developer/PRD.md), [첫 Feature Tasks](../../specs/001-project-document-analysis/tasks.md).

초기 Provider 조사와 평가 절차: [Solar Pro 4 Provider 평가](provider-evaluation.md). 현재 모델 실험과 검증 상태는 아래 최신 기록을 우선한다.

2026-09-25 확인된 Spring Boot → FastAPI 서비스 분리와 미합의 내부 계약은 [FastAPI 서비스 경계·계약 초안](fastapi-service-contract.md)에 기록했다. 기존 첫 Feature Plan·Tasks의 단일 Next.js 서버 구조는 재작성 전까지 구현 기준으로 사용하지 않는다.

AI 파트의 초기 작업 순서는 [FastAPI 구현 계획](fastapi-implementation-plan.md)과 [AI Developer Tasks](tasks.md)에 정리했다. 두 문서의 2026-09-25 구현 상태·미완료 표시는 당시 기록이며, 이후 기능별 검증 기록을 함께 확인해야 한다. 실패 건에서 수신한 LLM 원본 응답은 오류 추적용으로 최대 7일 보관한다.

이 폴더는 기능별 조사·설계·평가 자료를 정리하는 공간이다. 현재 AI 서비스 구현과 테스트는 `ai_service/agentfit_ai/`, `ai_service/tests/`에 있다.

기능별 구현은 사용자 요청에 따라 Spec → Plan → Tasks → 테스트 → 구현 → 검증의 SDD 순서로 진행한다. 첫 적용은 [Profile 후보 검증 Spec](01-profile-contract/spec.md)·[Plan](01-profile-contract/plan.md)·[Tasks](01-profile-contract/tasks.md)다. 기존 문서의 `src/` 경로는 단일 Next.js 서버 계획의 이전 기준이다.

## 현재 검증 경계 — 2026-09-30

- FastAPI 내부 분석 API, 인증·입력 제한, 동시 요청 제한, 취소·기한 처리와 격리 Worker가 구현돼 있다. [서비스 명세](11-fastapi-analysis-service/spec.md), [요청 수명 주기 검증](13-analysis-request-lifecycle/validation.md), [Linux 메모리 제한 검증](14-pdf-worker-memory-limit/linux-ci/validation.md).
- 사용자 확인 질문을 전달하는 `recoverable-solar`는 선택형 모드다. 제안·미해결 필드의 질문 완전성은 검증했지만 Spring·Frontend의 확인 및 저장 흐름은 미확인이다. [질문 계약 검증](11-fastapi-analysis-service/confirmation-suggestion-ack/validation.md).
- 후보 추출→원문 위치 확정→분류→검토 경로는 별도 평가 실험이다. 현재 HTTP 서비스의 기본 분석기가 아니다. [후보 우선 실험](04-analysis-provider/candidate-first-profile/validation.md), [원문 위치 확장](04-analysis-provider/candidate-source-occurrences/validation.md).
- 최신 분리 검토 H02는 응답 미완료로 실패했고 최초 기능 후보 누락도 남았다. [실제 결과](04-analysis-provider/candidate-split-review/validation.md). 실패한 호출의 위치·종료 사유·토큰 수를 확인하는 [호출 진단](04-analysis-provider/candidate-review-diagnostics/validation.md)을 진행 중이다.
- 단위 테스트·CI 통과를 실제 문서 의미 정확도나 Spring 저장 성공으로 간주하지 않는다. 독립 문서 품질, Spring 계약·저장·확인 및 실패 응답 7일 삭제의 통합 검증이 남아 있다. 운영 적용 완료를 선언하지 않는다.

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
