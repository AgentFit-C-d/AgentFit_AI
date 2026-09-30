# 통합 분석 입력 검사 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 승인대로 직접 구현한다.

**Goal:** 기존 Solar 민감값 검사를 통합 분석의 첫 외부 경계보다 앞에 적용한다.
**Architecture:** 기존 검사 함수 재사용, 문서와 문서 ID 선검사. 새로운 정책·의존성·응답 모델 없음.
**Spec:** specs/ai-developer/04-analysis-provider/integrated-input-guard/spec.md
**Tech Stack:** 기존 Python/unittest.

## Global Constraints

- branch feature/integrated-input-guard, base7d6f1b7, E:/AgentFit/tmp/worktrees/integrated-input-guard. 실제 H02 평가 checkout/driver 수정 금지.
- 문서/ID의 기존 입력·옵션 검사를 유지하고 패턴 차단은 AnalysisError/SENSITIVE_CONTENT, 외부 경계 호출0, trace 변이0.
- 가짜 값만 사용하고 실제 API/개인 문서/키 접근 없음. 정상 모델·Profile·호출 예산·HTTP 계약 유지.

## Review Focus

- 기본 LangExtract와 주입 extractor의 경계 전에 검사가 이루어지는지.
- document_id로 입력되는 값에도 같은 차단이 적용되는지.
- 직접 API key 포함과 잘못된 옵션의 기존 거절 동작을 바꾸는지.
- 기존 collector나 observer에 차단 입력 또는 실패 본문이 새로 남는지.
- 정상 문서에서 기존 전체 분석과 다른 결과를 만드는지.

### Task 1: 기존 검사 재사용 및 회귀 검증

**Files:** Modify ai_service/agentfit_ai/candidate_analysis_pipeline.py; Create ai_service/tests/test_integrated_input_guard.py; Modify specs/ai-developer/04-analysis-provider/integrated-candidate-analysis/README.md.
**Interfaces:** 함수 signature 유지. `_reject_sensitive` 재사용. 문서/ID의 민감 패턴은 extractor 전에 `AnalysisError('SENSITIVE_CONTENT')`.

- [x] **Step1 RED:** 문서 패턴 표본·ID 패턴·기본 및 주입 추출 호출0·collector/observer 보존·정상 전체 결과를 5개 테스트로 작성한다. `python -m unittest discover -s tests -p test_integrated_input_guard.py -v` Expected: 차단 부재 테스트 FAIL, 정상 경로는 기존 결과와 동일.
- [x] **Step2 implement:** 기존 옵션 검사 직후 문서와 ID에 기존 `_reject_sensitive`를 호출한다. 직접 key 포함 거절 동작은 유지한다. Expected: 새 정규식/로그/I/O 없음.
- [x] **Step3 GREEN:** 새 테스트와 전체 suite를 실행하고 README에 범위·거절 코드를 기록한 뒤 commit. task-done은 전체 suite. Expected: 모든 테스트 PASS(기존 플랫폼 skip 명시).

### Task 2: 독립 리뷰와 게시

**Files:** Create validation.md; Modify work/harness/integrated-input-guard/STATE.md 및 본 plan.
**Interfaces:** Task1 구현 revision의 전체 diff를 독립 리뷰1회. 기존 H02 실험의 revision과 혼합하지 않는다.

- [x] **Step1:** base부터 제품 구현까지 전체 리뷰. Critical/Important는 한 번 RED→GREEN 수정 및 전체 suite, Minor는 기록. Expected: 차단 결함 해결, 리뷰 범위/미판정 항목 기록.
- [x] **Step2:** feature push, 정확한 구현 revision CI 확인. 검증 문서 commit/push, task-done diffcheck. Expected: upstream 일치·CI success·문서형식 PASS. H02 결과와 실제 서비스 품질 미완료는 구분한다.

## 자체 검토

Task1 외부 경계0와 동작 보존을 Task2에서 독립 확인한다. 구현 중인 실제 평가와 checkout을 분리했으며 설정 변경·새 키 조회는 없다. 다섯 Review Focus는 Task1의 대응 테스트로 검증한다.
