# Integrated Analysis Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 통합 분석기의 선택형 설치와 실제 SDK 실행을 깨끗한 환경과 CI에서 검증한다.

**Architecture:** 별도 requirements 파일로 LangExtract를 고정한다. 별도 runtime_tests에서 실제 SDK·분석 흐름을 실행하고 외부 전송만 합성 응답으로 대체한다.

**Tech Stack:** Python3.13, unittest, LangExtract1.7.0, 기존 Solar/NVIDIA 어댑터, GitHub Actions.

**Spec:** specs/ai-developer/04-analysis-provider/integrated-analysis-runtime/spec.md

## Global Constraints

- 기본 Profile·HTTP·프롬프트·모델·호출/재시도 정책은 변경하지 않는다.
- 실제 API0, 키·개인 문서 읽기0, 기본 설치는 LangExtract 필수 아님.
- 깨끗한 로컬 `.venv`와 Ubuntu24.04/Python3.13 CI에서 검증한다.
- 직접 순차 구현, SDD 기록 보존, feature/integrated-analysis-runtime 커밋·push, 독립 최종 리뷰1회.

## Review Focus

- 선택형 SDK 부재가 CI에서 skip이나 기존 개발 venv로 숨겨지지 않는가: 실제 import 실패/깨끗한 설치 및 job 확인.
- 기본 추출기가 우회되지 않는가: SDK import와 extractor 미주입 전체 Profile 검사.
- SDK가 반복 인용의 anchor·위치를 유실하는가: 두 anchor와 각각0..1,6..7 위치 검사.
- 제공자 잘못된 JSON이 후속 호출이나 성공으로 이어지는가: safe stage 및 요청1회 검사.
- 여러 청크의 SDK 전송이 예산을 우회하는가: max_calls1의 두 번째 전송 차단 검사.

### Task 1: 선택형 설치와 실제 SDK 실행 게이트

**Files:**
- Create: `ai_service/requirements-integrated.txt`
- Create: `ai_service/runtime_tests/test_integrated_runtime.py`
- Modify: `.github/workflows/ai-linux.yml`
- Modify: `specs/ai-developer/04-analysis-provider/integrated-candidate-analysis/README.md`
- Create: `specs/ai-developer/04-analysis-provider/integrated-analysis-runtime/validation.md`

**Interfaces:**
- Consumes: `analyze_integrated_candidates(document, document_id, solar_key, nvidia_key, solar_transport=..., nvidia_transport=..., max_calls=...)`; `extract_candidates(document, key, transport=...)`; `freeze_candidates(document, extractions)`.
- Produces: `python -m pip install -r ai_service/requirements-integrated.txt -r ai_service/requirements-dev.txt`; ai_service에서 `python -m unittest discover -s runtime_tests -v`의 성공/실패 종료 상태. 공개 Python/HTTP 인터페이스 변경 없음.

- [x] **Step 1:** 실제 SDK 통합4테스트를 먼저 작성한다. 전체 Profile 10필드와 호출5회, 반복 인용 anchor2개·위치2개, 잘못된 JSON에서 EXTRACTION_FAILED·후속호출0, 긴 문서의 예산1에서 CALL_BUDGET_EXCEEDED·실제전송1을 검사한다. 기대 값은 합성 문서를 손으로 계산한 literal을 사용한다.
- [x] **Step 2:** 기존 기본 테스트 Python에서 `-m unittest discover -s runtime_tests -v`를 실행한다. Expected: LangExtract 부재로 nonzero. 깨끗한 `.venv`를 만들고 기본·개발 requirements만 설치한 뒤 같은 실패를 확인한다.
- [x] **Step 3:** 선택형 requirements에 `-r requirements.txt`와 `langextract==1.7.0`을 추가한다. `.venv`에서 해당 파일을 설치하고 `python -m pip check`를 실행한다. Expected: exit0/호환성 오류0.
- [x] **Step 4:** `.venv`에서 `python -m unittest discover -s runtime_tests -v`를 실행한다. Expected: 4/4, skip0, 실제 API0. 기존 어댑터가 가정을 위반하면 원인을 확인하고 최소 수정의 근거를 ledger에 기록한다.
- [x] **Step 5:** 선택형 Linux CI job과 한국어 설치·검증 README를 추가한다. 별도 job이 선택형·개발 requirements 설치, pip check, runtime_tests, 기존 전체 suite를 순서대로 실행한다.
- [x] **Step 6:** 기존 기본 환경과 새 `.venv`에서 각각 `python -m unittest discover -s tests -q`를 실행한다. Expected: Windows996건/990통과6제외. 새 선택형 테스트4건은 별도 집계한다. `git diff --check`와 변경 범위를 검토한다.
- [x] **Step 7:** product/config/test/docs를 커밋한다. Task 완료 명령은 `.venv`로 runtime_tests와 tests 전체를 모두 실행하는 PowerShell 검증 스크립트이며, 하나라도 실패하면 nonzero로 종료한다. 최종 독립 리뷰 및 필요한 수정 후 push하고 정확한 구현 커밋 CI의 두 job을 확인한다.

## 자체 검토

모든 요구사항은 Task1에 대응한다. 한 deliverable로 공유 작업 인터페이스 없음. 설치 결함은 실제 import 실패와 깨끗한 설치로 검증하며 requirements 문자열 비교용 테스트를 만들지 않는다. 기존 전체 테스트와 실제 SDK 테스트는 목적·분모를 구분한다. 자율 진행 승인에 따라 재승인 질문을 하지 않는다.
