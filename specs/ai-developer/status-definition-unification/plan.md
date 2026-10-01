# Status Definition Unification Implementation Plan

> 직접 구현은 superpowers:executing-plans 절차를 따른다. 사용자 승인된 최소 수정안을 재승인받지 않는다.

**Goal:** status 정의만 바꾼 UC/US 한 쌍으로 잘못된 확정과 부정·상충 보존을 비교한다.
**Architecture:** 과거 저장 요청을 기준선으로 사용하고 별도 harness가 status 문장 교체만 수행한다.
원래 gate·점수 함수·8회 호출 제한기를 재사용하며 서비스는 연결하지 않는다.
**Tech Stack:** Python/unittest, 기존 NVIDIA transport.
**Spec:** `specs/ai-developer/status-definition-unification/spec.md`.

## Global Constraints

총32개/주30개, max8회, retry0, timeout600초/전체5400초. 무료 확인 만료 시 중단.
모델·원문·후보·정답·다른 분류 지침·스키마·서버 판정 변경0. 기존 자료 보존.

## Review Focus

- status 교체가 다른 분류 지침을 건드리거나 중복 정의를 남기는지: payload의 허용된 교체 외 차이 검사.
- 저장 요청의 변경·원본 유실: 기존 hash 및 실제 요청 동일성 확인 후 freeze.
- 부정과 불확실성을 other/irrelevant로 감추는지: 고정 응답으로 원시 판정·gate 결과 보존 검사.
- LS15 counter가 존재한다는 것과230행을 선택한 것을 혼동하는지: 잘못된 counter와 정확한 counter 대조.
- 무료 만료·모델 실패·실행 중단 후 재호출: 기존 gate 및 새 live marker 경로에서 호출0/1 제한 검사.

## Task1: 독립 비교 harness와 로컬 검증

Create `work/harness/status-definition-unification/{experiment.py,evaluate.py,STATE.md}`,
`specs/ai-developer/status-definition-unification/{status-definition.txt,status-edits.json}`,
`ai_service/tests/test_status_definition_unification.py`.

- [x] RED: 허용 교체만 발생, UC원본 동일, 입력 누출0, 진단 집계, 부정/보류 보존, 실패 중단 테스트.
- [x] GREEN: `unify_status(system)`, `prepare_package()`, `diagnostics(result,gold,document)` 및 freeze/live 구현.
- [x] 기존13개와 신규 테스트 및 전체 unittest suite 실행. 의미 정확도는 로컬 테스트로 주장하지 않는다.
- [x] 독립 코드 검토 후 필요한 결함만 수정, 커밋. Critical/Important/Minor0.

## Task2: 한 쌍 실행과 보고

- [ ] 무료 범위 현재 유효성·기존 결과 해시 확인; 자료·코드 freeze; 최초 live1회만 실행.
- [ ] 최대8회로 UC/US 한 쌍을 실행. 실패하면 나머지 미실행 표시, 재시도0.
- [ ] 같은 정답·분모로 문서별 지표 및 LS07/LS15 별도 보고. 실제 기록과 요청 동등성 재검증.
- [ ] 결과/상태를 저장하고 feature 브랜치 push. 서비스 적용·큰 goal 재개 없이 종료.
