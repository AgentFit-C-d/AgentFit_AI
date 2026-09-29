# 원문 선택자 간결 의미 검토 구현 계획

**목표:** 원문 선택자 분석에서 의미 검토 응답을 줄이고 서버 검증을 유지한다.

**구조:** `SourceSelectorSolarAnalyzer`의 opt-in `compact_review`가 기존 `review_payload`·`normalize_compact_review`를 호출한다. NVIDIA 하위 분석기도 이 경로를 상속한다. 공개 평가 CLI에 플래그와 실제 출력 한도를 기록한다.

**대상:** `source_selector_analysis.py`, `public_holdout_evaluation.py`, 관련 테스트와 이 폴더의 검증 기록.

## 작업 1: 검토 계약 연결

- [x] 실패 테스트: 정상 간결 이슈가 기존 의미 수정으로 이어지고, 잘못된 ID·줄·형식은 보류되며 기본 검토 응답은 변하지 않는다.
- [x] 간결 payload 전송과 정규화·안전 오류 매핑을 opt-in으로 구현한다.

## 작업 2: CLI 선택과 안전 진단

- [x] 실패 테스트: 플래그는 원문 선택자에만 허용되고 plan의 검토 상한이 4096이며 기본 경로는 유지된다.
- [x] 평가 CLI에 `--compact-review`를 연결한다.

## 작업 3: 실제 평가와 결정

- [x] 전체 테스트를 실행한다.
- [x] 이미 튜닝에 쓴 Campfire 1건을 300초 전체 기한에서 Solar 간결 검토로 시험한다. 실패 사유를 좁힌 뒤 5건 확대 여부를 결정한다.
- [x] 결과·원문/키 비저장 확인을 `validation.md`에 기록하고 feature 브랜치를 push해 Linux CI를 확인한다.

## 작업 4: 출력 한도 재진단

- [x] Campfire의 간결 medium 검토가 4096/4096으로 미완료되면, 실패 테스트부터 `compact_review_effort=low`를 선택형으로 추가한다.
- [x] 같은 Campfire를 low에서 재실행해 검토 응답 완성·검증 오류·부분 정답·경과를 기록한다. 유효하면 같은 PRD 5건으로 확대한다.

## 검토 초점

- 잘못된 targetId가 기존 배열의 다른 항목을 수정해서는 안 된다.
- `missing`의 원문 줄이 없으면 조용히 통과시켜서는 안 된다.
- 모델 응답에 없던 `checkedFields`를 서버가 채울 때 10개 필드 검증 의무가 약해질 수 있으므로 결과의 오류·누락을 실제 문서로 확인한다.
- 숫자 진단과 결과 JSON에 원본 응답이나 문서 전체가 남지 않아야 한다.
