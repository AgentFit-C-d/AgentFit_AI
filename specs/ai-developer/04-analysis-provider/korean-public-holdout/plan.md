# 한국어 공개 문서 독립 평가 구현 계획

**목표:** 한국어 공개 프로젝트 README 5건의 고정 정답표를 최초 1회 독립 평가에 사용한다.

**구조:** 기존 검증기·채점기는 유지하고 manifest의 기대 partition을 인수로 받는다. CLI는 기본 영어 튜닝 코퍼스를 유지하며 명시적 경로일 때만 새 manifest를 사용한다. 결과 파일은 현재처럼 원문과 Profile을 제외한다.

**대상:** `ai_service/agentfit_ai/public_holdout.py`, `public_holdout_evaluation.py`, `ai_service/tests/test_public_holdout.py`, 이 폴더의 `manifest.json`·`validation.md`.

## 작업 1: partition 경계

- [ ] `load_manifest(path=MANIFEST, *, expected_partition="tuning")` 실패 테스트: 기대값 불일치, 지원하지 않는 partition, 기존 기본값.
- [ ] 테스트 실패 확인 후 정확한 기대값만 허용하도록 구현한다.
- [ ] 관련 테스트 통과.

## 작업 2: CLI 입력 경계

- [ ] 별도 manifest 경로·partition을 선택하고 결과 plan에 실제 partition·manifest 해시를 쓰는 실패 테스트를 만든다. 잘못된 입력은 모델 호출 전 실패해야 한다.
- [ ] 테스트 실패 확인 후 CLI 인수와 선택 함수를 최소 변경으로 구현한다.
- [ ] 관련 테스트 통과.

## 작업 3: 고정 코퍼스

- [ ] 5개 고정 커밋의 SHA-256 및 수작업 별칭·정확 인용을 manifest에 기재한다.
- [ ] 전체 문서의 해시·UTF-8·인용 유일성 검증을 실행한다.
- [ ] 최초 모델 호출 전에 manifest를 스테이징하고 diff를 확인한다.

## 작업 4: 1회 라이브 평가와 기록

- [ ] 고정 manifest로 문서당 한 번 `solar-pro4`를 호출해 ignored 로컬 결과에 기록한다.
- [ ] 결과·한계·산출물 해시를 validation에 적고 manifest를 `tuning`으로 전환한다.
- [ ] 전체 테스트·diff check·feature 브랜치 push·Linux CI를 확인한다.

## 검토 초점

- 같은 README 안의 목차/본문 중복 인용: 인용이 유일하지 않으면 호출 전 거부한다.
- 큰 HTML·이미지 마크업 문서: 100KB 상한과 UTF-8 조건을 지킨다.
- 예상과 다른 partition: 명시적 기대값과 manifest 값이 다르면 평가하지 않는다.
- 실패한 분석도 결과를 남기고 다른 문서는 이어서 처리한다.
- 일부 정답만 채점한 결과를 전체 정확도로 해석하지 않는다.
