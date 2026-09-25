# Implementation Plan: AI Profile 후보 검증

**Spec**: [spec.md](spec.md)
**Constitution**: [2.0.0](../../../.specify/memory/constitution.md)
**Status**: 2026-09-25 설계 완료, 구현 검증 전

## 기술 범위

FastAPI 서비스에 들어갈 순수 Python 검증 모듈을 먼저 만든다. 현재 로컬 Python 3.12.14에서 표준 라이브러리만으로 실행 가능한 테스트를 사용한다. HTTP·Provider·DB 의존성을 두지 않아 Full Stack A 내부 계약과 독립적으로 값/근거 계약을 고정한다.

| 산출물 | 경로 | 역할 |
| --- | --- | --- |
| 순수 검증 모듈 | `ai_service/agentfit_ai/profile.py` | 입력 후보 구조·근거 검증, 출처·미확정 계산 |
| 테스트 | `ai_service/tests/test_profile.py` | 정상·실패·Unicode 경계 검증 |
| 사전 정답 | `specs/ai-developer/02-evaluation-fixtures/starter-cases.json` | 합성 입력과 기대값 |

## 계약

입력은 추출 텍스트, 문서 식별자, 후보 객체 `{data, evidence}`다. `data`는 10개 필드를 정확히 포함하고 `evidence`도 같은 필드 집합에 각 위치 배열을 가진다. 각 위치는 `start`와 `end` 정수다.

성공 결과는 `{data, sources, evidence, unknownFields}`다. 근거 위치에는 현재 문서 식별자를 붙인다. 오류는 고정 코드와 안전한 필드명만 반환하며 내용은 포함하지 않는다. 배열 값의 각 항목은 적어도 한 근거 위치의 원문에 포함돼야 한다.

값 정규화, 동의어 추론, 문맥 의미 판정은 하지 않는다. 원문과 다른 표현은 실패시켜 후보를 다시 검토하게 한다. 이 엄격함은 [상위 데이터 모델](../../001-project-document-analysis/data-model.md)의 원문 표현 사용 원칙에 따른다.

## 구현 순서와 검증

1. 명세·계획·작업을 고정하고 합성 정답을 읽는 테스트를 작성한다.
2. 테스트 실패를 확인한 뒤 구조·값 검증을 구현한다.
3. 근거 범위·값 대응·code-point 위치를 검증한다.
4. 정상·오류 테스트를 실행하고 결과를 `validation.md`에 기록한다.

### Constitution 점검

- III LLM Is Not Authority: 모델 후보를 검증하고 미정값을 계산한다.
- V Secret Isolation: 오류에 입력·응답 내용을 넣지 않는다.
- VIII Minimal MVP Scope: 순수 검증 모듈만 구현하며 서비스·DB를 추가하지 않는다.
- IX Testable Requirements: 합성 사례와 실패 경계를 독립 테스트한다.

## 남은 통합 조건

FastAPI가 모델 응답의 인용문을 위치로 바꾸는 과정과 의미상 확정 판단은 별도 SDD 대상이다. Spring Boot의 최종 검증·저장 계약은 [서비스 경계 초안](../fastapi-service-contract.md)에서 합의한다. 이 모듈의 테스트 통과만으로 전체 AI 분석 품질을 통과 처리하지 않는다.
