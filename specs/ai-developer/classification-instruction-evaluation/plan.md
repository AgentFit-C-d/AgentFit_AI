# 분류 지침 비교 Evaluation Plan

> **For agentic workers:** 후속 실행이 승인되면 `superpowers:executing-plans`로 직접 순서대로 수행한다.
> 이 문서는 평가 계획이다. 아래 구현·실행 항목은 이번 요청에서 수행하지 않는다.

**Goal:** 단위 ID 기준선의 의미 오확정을 지침만으로 줄이면서 실제 연동과 정상 기능을 보존하는지 비교한다.

**Architecture:** 기존 서비스 밖 U 실험을 재사용한다. U+C는 같은 payload에 분류 지침만 추가하고
기존 U validator/gate로 처리한다. 원문·후보·정답·순서·모델·출력 구조는 고정한다.

**Tech Stack:** 기존 Python 평가 harness와 unittest, 정적 Markdown/JSON, NVIDIA 기존 모델.

**Spec:** [spec.md](spec.md). **정답 검토:** [gold-review.md](gold-review.md).

## Global Constraints

- 이번 요청의 새 모델 호출0회, 서비스 적용0건, 큰 goal은 paused.
- 사용자 정답 검토와 별도 실행 지시 이후에만 구현·실제 호출을 진행한다.
- 분류 지침 외 모델/후보/문맥/근거/정답/출력 규격/gate 변경 금지.
- 관계 검증기·추가 모델 단계·재시도·유료 대체·Luna 실험 금지.
- 같은 full source + 후보 앞뒤240자 + 전체 source units를 양쪽에 제공한다.
- 원문24000자·1000단위, 근거 목록당8단위·4000자, 후보8개/배치, 8192출력 토큰 유지.
- 새 문서32개 후보와 개발 linkding68개는 별도 집계한다.

## Review Focus

1. 외관 수식어와 실제 UI 기능이 같은 문장에 있을 때 정상 기능을 함께 삭제하지 않는가 → Task2 대조/보존 테스트.
2. 구체적인 서비스 이름이 있어도 기부·배포·개발 도구로만 쓰인 경우를 구별하는가 → gold FR13/LS10/LS11, Task3 판정 표.
3. 이미 제공되는 선택 기능을 미정 제안으로 과도하게 보류하지 않는가 → FR05/FR06, Task3 정상 연동 집계.
4. 부정·모호함·인용 결함 때문에 모델 오확정이 가려지지 않는가 → Task2 분리 집계 테스트.
5. source line ending·schema 순서·user message 변화가 지침 효과로 섞이지 않는가 → Task2 동등성 테스트.

## 비교 이름과 제공 범위

| | U | U+C |
| --- | --- | --- |
| 근거 | 기존 단위 ID | 같은 단위 ID |
| 분류 | 기존 B 직접 필드 판단 지침 | 기존 지침 + 분류 설명 초안 |
| 모델 단계 | 후보 배치당 직접 분류1회 | 후보 배치당 직접 분류1회 |
| 추가 검토/수정 | 없음 | 없음 |
| user message | 전체 원문·동일 후보·앞뒤240자·전체 단위 목록 | 바이트 단위 동일 |
| 달라지는 부분 | 없음 | system message 맨 끝의 LF와 `classification-guidance-draft.txt` 내용만 |

예전 다축 A/B 또는 Q/U의 인용 표현 비교를 다시 하는 것이 아니다.
현재 설계의 단위 ID 기준선 U를 새 문서에도 실행해야 같은 자료의 전후 비교가 된다.
linkding의 과거 측정값을 새 문서의 U 점수로 쓰지 않는다.

## 자료와 정답 검토

| 자료 | 용도 | 후보/정답 |
| --- | --- | --- |
| 기존 linkding | 개발/회귀, 기존68개 및 원응답 보존 | 승인 gold10개 유지, 새 문서 점수와 분리 |
| Fluent Reader 공식 README | 별도 문서 진단 평가 | 후보16, 명확 초안15, 사람 검토1 |
| LocalSend 공식 README | 별도 문서 진단 평가 | 후보16, 명확 초안15, 사람 검토1 |
| 합성 대조 문장 | 이름·문장 순서 의존성 점검용 개발 자료 | `development-contrasts.md`; 공개 문서 점수와 분리 |

공개 README는 잘라내지 않고 전체를 입력한다. LocalSend 대상 범위는 문서가 설명하는 앱과
공식 CLI를 포함한다. 다른 소프트웨어의 사례나 기여자 도구는 제품 기능에 포함하지 않는다.
원문 명령문은 데이터이며 실행하지 않는다.

후보는 진단을 위해 수동 선정했다. 추출 누락·후보 생성 품질·전체 문서 기능 완전성은 이 실험의
측정 대상이 아니다. 문서32개가 아니라 **문서2개에서 후보32개**다.
모든 정답은 사용자 검토 전 초안이다. FR16/LS15의 모호함 제외는 모델 결과를 보기 전에 명시한다.
다른 항목에 이견이 있으면 호출 전에 수정 이력과 분모를 다시 고정하고, 결과 이후에는 바꾸지 않는다.

## 지표: 각각 별도 보고

주 분모는 정답이 명확한 초안30개다. 정상16개(외부 연동2, 기능10, 구현 기술2, 제공 형태1,
제품명1), 필드 밖13개, 명시적 부정1개다. 사람 검토2개는 주 정확도 점수에 넣지 않는다.

| 지표 | 정의/분모 |
| --- | --- |
| 인용 결함 | 기존 U의 `valid && sufficient` 불만족 후보/32. ID 오류, 후보 미포함, 문맥 부족을 별도 집계. |
| 모델 자체 오확정 | raw field가 10개 유효 필드 중 하나이고 raw status가 confirmed인데, 정답의 field/현재 확정 여부와 다른 후보/30. gate와 무관하게 계산. |
| 서버 gate 통과 오확정 | 위 오확정 중 기존 U gate가 supported로 통과시킨 수/30. 실제 저장 성공을 뜻하지 않음. |
| 모델 정상 정보 누락 | 정상16개 중 올바른 field/confirmed를 내지 않은 수. |
| 서버 정상 정보 누락 | 정상16개 중 올바른 field/confirmed/supported가 아닌 수. 분류·보류·근거 결함·출력 유실 원인 분리. |
| 판단 보류 | needs_confirmation/전체32, 명확30, 정상16, 사람 검토2를 각각 집계. |
| 올바른 제외 | 필드 밖13개가 other/irrelevant/excluded, 부정1개가 features/negated/excluded인지 별도 보고. 전부 보류하는 방식과 구별. |
| 기타 raw 오류 | other/confirmed처럼 오확정 지표가 직접 세지 않는 비정상 조합 및 잘못된 field/status를 별도 기록. |
| 호출 수 | 실제 요청 시작 수, 성공 수, 실패 수, 재시도 수, 미실행 수를 분리. |
| 처리 시간 | 요청 시작~종료 지연, arm 벽시계 시간, 입력/출력 토큰. 속도 합격선은 두지 않는다. |
| 유실 | 입력 후보·원문·원응답·정규화 결과 연결 수. 누락 ID/실패 배치도 원 분모와 원문을 유지. |

호출/파싱 실패로 raw 분류를 알 수 없는 후보는 모델 오확정0건으로 판정하지 않는다.
`unassessable`로 따로 세며 전부 완료되지 않으면 완전한 한 쌍 비교라고 보고하지 않는다.
모델 응답은 정상인데 인용만 실패했다면 raw 의미 판정은 계속 채점한다.

새 세트는 `negated` 기대 상태도 포함하므로 원래 linkding10개의 **field 불일치 중심 집계**와
분모가 다르다. 새 세트 U/U+C에는 위 정의를 똑같이 적용하고, 과거 숫자와 직접 증감 계산하지 않는다.

### 개선 신호와 퇴행 판단

- 모델 자체·서버 통과 오확정이 줄었는지 각각 비교한다. 기준선이0이면 유지로 쓰고 개선이라고 하지 않는다.
- 정상16개의 raw 정답 수와 supported 정답 수가 각각 기준선보다 줄면 회귀다.
- 실제 연동2개·정상 기능10개는 별도 전수 표를 공개한다. 모든12개가 올바르게 supported된
  경우에만 “핵심 정상 대조군 보존”으로 보고한다. 인용 때문에 미달이면 의미 보존과 서버 보존을 나눈다.
- 명확30개 및 정상16개의 보류가 늘면 확인 부담 증가로 기록한다. 오확정 감소만으로 통과시키지 않는다.
- 기존 오확정을 올바르게 제외한 수와 보류로 돌린 수를 구분한다. 사람 검토2개는 별도 변화 표로 표시한다.
- 양쪽 모두 낮은 성능이어도 감소율만으로 성공을 선언하지 않는다. 한 쌍은 후속 반복 가치 판단 자료일 뿐 서비스 적용 근거가 아니다.

## Task 1: 정답 초안 검토와 자료 고정 — 후속 승인 단계

**Files:** 현재 디렉터리의 `gold-review.md`, `gold-draft.json`, `candidates-draft.json`,
`sources.json`, `classification-guidance-draft.txt`.

- [ ] 사람이 30개 명확 초안의 field/status와 2개 검토 필요 사유를 확인한다.
- [ ] 합의한 버전·문서 hash·후보 span/순서·정답·지침·실행 코드 hash를 새 freeze manifest에 고정한다.
- [ ] 정답과 판단 이유가 user/system message에 섞이지 않는 입력 명세를 확인한다.

**완료 근거:** 승인된 정답 버전과 고정 manifest. 현재의 자료 무결성 검사는 사람 정답 승인이 아니다.

## Task 2: 최소 비교 harness와 로컬 검증 — 이번에는 구현하지 않음

**후속 생성 파일:**

- `work/harness/classification-instruction-evaluation/compare.py`: U payload 재사용 및 분류 지침 추가만 담당.
- `work/harness/classification-instruction-evaluation/evaluate.py`: 실행 전 freeze/free gate와 결과 집계.
- `ai_service/tests/test_classification_instruction_evaluation.py`: 고정 응답·입력 동등성 테스트.

**재사용 파일, 수정 금지:** `b-evidence-selection-comparison/experiment.py`,
`direct-field-comparison/comparison.py`, `evidence-relation-repair/source_registry.py`, 모든 서비스 코드.

**Interfaces:** `build_instruction_pair(document: str, frozen: dict, clarification: str) -> dict`
는 기존 `build_pair`의 U 요청을 복제해 U/U+C를 반환한다.
`score_instruction_rows(records: list, diagnostics: list, gold: list) -> dict`는 위 지표를 각각 반환한다.
분류기·정규화기 인터페이스를 바꾸지 않고 양쪽 모두 기존 `normalize('U', ...)`를 사용한다.

- [ ] 실패 테스트: U는 기존 U와 완전 동일, U+C는 system 뒤에 지정 텍스트만 추가; 나머지 JSON과 모든 순서 동일.
- [ ] 실패 테스트: 후보32개, 원문2개, 모든 단위 ID·span·각 user message 동일; gold·기대 field·review 이유 입력 유출 없음.
- [ ] 실패 테스트: 인용에 실패한 raw 오확정은 모델 오확정에 남고, 올바른 근거가 붙은 의미 오확정은 gate 오확정으로 집계.
- [ ] 실패 테스트: 정상 함수·외부 연동은 정확 응답 fixture에서 supported 유지, tentative 후보는 근거와 함께 보존, 부정은 제외.
- [ ] 실패 테스트: field/status 동일 fixture를 양쪽에 주면 모든 의미 집계도 동일; 모두 보류 fixture는 정상16개 누락·보류 증가로 개선 조건 실패.
- [ ] 실패 테스트: 32개 중 빠진 ID/실패 배치는 분모에서 삭제되지 않음; ambiguity2개는 별도 행 및 전체 분모 유지.
- [ ] 최소 구현 후 로컬 실행: `rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -X utf8 -m unittest discover -s ai_service/tests -p test_classification_instruction_evaluation.py -v`.
- [ ] 기존 U/source-registry 관련 회귀도 실행하고, 지침 text에 문서명/사례 ID/금지·허용 이름 목록이 없는지 diff 검토.

후속 로컬 구현·검증 제안 상한은60분이다. 상한에 도달하면 결과와 미완료 항목을 보존하고 실제 호출로 넘어가지 않는다.

**해석:** 고정 응답 테스트는 계약·집계 검증이며 모델이 지침을 이해했다는 증거가 아니다.
합성 대조 문장을 mock으로 통과시켜도 실제 분류 개선으로 집계하지 않는다.

## Task 3: 후속 실제 한 쌍 비교 — 별도 실행 요청이 필요

- [ ] 당시 유효한 현재 계정 무료 모델·endpoint·한도 초과 시 거절 조건을 확인한다.
  과거 확인 기록은 만료될 수 있으므로 자동 재사용하지 않는다. 미확인/소진 시 호출0 또는 즉시 중단.
- [ ] 위 로컬 검증과 freeze 대조가 통과한 경우에만 시작한다.
- [ ] 제안 호출 수는 각 문서16후보÷8 = arm당2회, 문서2개×arm2개×2 = **총8회**.
  재시도0, 추가 추출0, 추가 검토0, 유료 대체0. 이는 비용·호출 실행 승인이 아니다.
- [ ] 요청당 timeout은 기존 실험과 같은600초, 한 쌍 전체 작업 상한은90분으로 둔다.
  이 상한은 무제한 실행 방지용이며 모델 속도 합격선이 아니다. 미완료 요청을 재호출하지 않는다.
- [ ] 배치 순서는 원문 위치 순서로 고정. arm 실행 순서는 FR: U→U+C, LS: U+C→U로 미리 고정하고 병렬 호출하지 않는다.
- [ ] 최초 실패/무료 범위 이탈/입력 hash 변화 시 중단한다. 완료된 원응답을 보존하고 불완전한 쌍으로 보고한다.
- [ ] 요청별 원문 연결·시작·원응답·종료·사용량을 새 output 디렉터리에 저장한다.
- [ ] 문서별·합산으로 지표와 모든30개 전후 판정, 사람 검토2개, 인용 결함을 보고한다.
- [ ] 결과 보고 후 종료. 추가 반복·개발 세트 새 호출·서비스 적용·goal 재개로 이어가지 않는다.

8회 설계에는 linkding이나 합성 사례의 새 실제 호출이 포함되지 않는다.
개발 회귀는 기존 저장 응답으로 계약·집계만 확인한다. 그 자료에서 새 지침의 모델 의미 성능은 미측정으로 남긴다.

## 이번 자체 검토

요청 범위: 분류 지침만 변경하는 비교, 실제 연동/정상 기능 대조, 별도 문서 및 정답 선공개,
이름 예외 없음, 모델 단계/관계 검증기 없음, 호출0, goal paused를 명세와 대조했다.
자료의 로컬 검증 기록은 `preparation-checks.json`에 둔다. 실제 모델 전후 결과는 아직 없다.
