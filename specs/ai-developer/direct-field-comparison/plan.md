# 직접 필드 판단 비교 계획

> **실행자:** 이후 실행을 명시적으로 지시받으면 superpowers:executing-plans로 직접 구현한다.
> **이번 요청:** 계획 작성 후 종료. 아래 작업은 모두 미래 작업이며 실행하지 않았다.

**Goal:** 같은 후보·원문에서 역할 enum을 줄이는 것이 오확정과 정상 누락을 함께 줄이는지 판단한다.
**Architecture:** 서비스 밖 평가 하네스에서 저장 후보를 주입하고 분류 단계만 교체한다.
각 모델 원응답 → 서버 판단 → 같은 로컬 Profile 변환까지 각각 보존한다.
**Tech Stack:** 기존 Python/원문 근거 검증기/NVIDIA 전송기. 새 의존성 없음.
**Spec:** [spec.md](spec.md), **검토할 정답:** [gold-review.md](gold-review.md).

## 1. 고정 입력과 비교 단위

- [input-manifest.json](input-manifest.json)의 기존 원문·trace·응답·gold 해시를 검증한다.
- `live-linkding-after/trace.json → stages.grounded`의68개 후보와 rejected24개를 그대로 사용한다.
  before의 grounded와 완전 일치해야 한다. `_source_mention`으로 원문/앞뒤240자/위치를 생성한다.
- 68개를 원래 순서로8개씩 나눠9묶음. A/B마다 동일 묶음/원문 byte-equivalent 입력.
- 원래 없는 후보는 만들지 않는다. 거절24개를 새 분류 결과처럼 처리하거나 숨기지 않는다.
- 기존 원본은 읽기 전용. 이후 새 결과는 독립 출력 폴더에 append-only로 보존한다.

## 2. 두 방식의 계약

### A — 현재 의미 역할 분류

현재 `candidate_semantic_assessment.assessment_payload`와
`validate_assessments / semantic_labels`를 수정 없이 사용한다. 모델의 field/modelStatus와
서버의 supported/needs_confirmation/excluded를 모두 기록한다.

### B — 최종 필드 직접 판단

평가 전용 응답 형태:

```json
{
  "decisions": [{
    "id": "배치에 있는 후보 ID",
    "field": "기존 10필드 또는 other",
    "status": "confirmed | tentative | negated | irrelevant",
    "support": [{"quote": "원문 그대로의 지지 문맥", "occurrence": 0}],
    "counterEvidence": []
  }]
}
```

id당 정확히1행. 후보 값/새 ID/새 필드/새 위치/자유롭게 합친 기능을 출력하지 않는다.
quote 계약은 A와 동일(최대4개, 각2000자, 원문 등장 순서). 전 문서에서 같은 대상·시점의
상충 근거를 찾고 불명확하면 tentative를 선택하도록 지시한다. 이름·프로젝트 ID 전용 예시는 넣지 않는다.

B 서버 규칙:

- 모든 ID 및 schema 검증. 누락/중복/손상 응답은 batch failure로 보존하고 정상 실행에 포함하지 않는다.
- 정확한 지지 문맥이 해당 후보 occurrence를 포함해야 한다. 근거 부족/위치 모호/반대 근거 존재는 보류.
- 유효 근거를 가진 known-field/confirmed는 모델 제안 supported.
- 유효 근거를 가진 other/irrelevant 또는 명시적인 negated는 excluded로 기록.
- tentative 및 other/confirmed 같은 모순은 needs_confirmation. 후보와 근거는 남긴다.
- 단어 존재만 검증한 것이 의미 정확성의 보장이 아님을 명시하고 정답표와 별도 평가한다.

기존 A에 필요한 mentionKind/의미 축을 B에 가짜로 채우지 않는다. 양쪽 결과를 평가용
공통 행(`id, raw_field, raw_status, verdict, support, counterEvidence, failure_reason`)으로만
맞춘다. 공개 API 및 영속화용 modelDecisions는 변경하지 않는다.

## 3. 측정 위치와 지표

| 지표 | 단위·분모·판정 |
| --- | --- |
| 오확정 | 정답10개 중 잘못된 필드/음성 후보를 supported로 제안한 occurrence 수. 원모델 confirmed 오류와 서버 통과 오류를 따로 표기 |
| 정상 누락 | 정상6개 중 올바른 필드의 supported가 없는 수. 보류/제외/오필드/기록유실을 하위 사유로 분리 |
| 판단 보류 | 전체68개 및 주 정답10개 각각 needs_confirmation 수. 정상6개 중 불필요한 보류도 별도 기록 |
| 기록 유실 | 68개 중 출력 기록 없는 ID 수. 단순 보류와 구분 |
| 호출 수 | 시작/반환/실패/재시도 각각 실제 전송 횟수. 로컬 재생은0. 계획9회를 실측처럼 쓰지 않음 |
| 시간 | 모델 호출별 wall time, 전체 분류 경과, 로컬 검증/후처리 시간을 따로 기록. 완료3회의 중앙값·최소·최대 및 개별값 |

잘못된 필드로 확정하면 오확정과 정상 누락에 동시에 해당할 수 있다. 합산 점수를 만들지 않는다.
모델의 field/status가 맞는데 A의 역할 enum 모순으로 서버에서 보류된 경우도 따로 집계한다.

공통 `project_candidate_profile` 재생으로 최종 제안에서 사라지는 항목도 측정하되,
분류 결과와 후처리 누락을 분리한다. 그 결과는 실제 `/internal/v1/analyze` 실행 결과가 아니다.
기존 rejected24개 때문에 최종 필드 확인 의무가 남으므로 질문 객체 수를 의미 보류 수로 대체하지 않는다.

시간 초과/503/한도 거절/schema 실패는 평가 실패다. 빈 출력을 오확정0 또는 정상 누락6으로
점수화하지 않는다. 실패율과 완료 coverage를 별도 보고한다. 부분 결과는 조사용으로만 보존한다.

## 4. 진행 순서 — 이후 실행 지시가 있을 때

- [ ] 사람에게 gold-review G01–G10과 PWA 경계를 먼저 확인받고 버전/해시를 동결한다.
- [ ] 미래 파일 `work/harness/direct-field-comparison/evaluate.py`와 분리된 B 응답 검증기를 작성한다.
  동일 입력 digest/배치, 누락ID·중복·근거 오류·보류 보존·계약 실패 채점 제외를 로컬 테스트한다.
- [ ] 저장된 A 원응답/기록 재생은 원인 재현용으로만 사용한다. B의 정답을 주입한 고정 테스트는
  평가기 검증이라고 표시한다. 이것을 B의 실제 정확도로 보고하지 않는다.
- [ ] 비용 없는 로컬 검증 후, 기존 무료 대상/endpoint 조건과 실제 실행 권한이 유효할 때만 A/B 호출한다.
- [ ] 3쌍 실행: 1회 A→B, 2회 B→A, 3회 A→B. 같은 pair 안에서는 문서·후보 순서가 같다.
  batch8·temperature0·medium·8192·동일 DeepSeek 모델. 동시 실행하지 않는다.
- [ ] 분류 후 GLM 검토/수정 호출 없이 공통 로컬 후처리만 실행한다. 단계별 지표와 누락 사유를 기록한다.
- [ ] 방식 이름을 가린 채 정답 밖 출력을 검토하고 오류/불명확 항목을 별도 표에 남긴다.
- [ ] 모든 pair의 개별 결과와 중앙값·범위를 보고하고 채택/보류를 결정한다. 서비스 적용은 별도 범위다.

## 5. 예산과 중단 조건

- **이번 단계: 모델 API 호출0, 구현0.** CI 조회와 문서 작성만 한다.
- 이후 기본 평가: 68후보/8 = 방식당9호출, A/B×3회 = **최대54회**, 자동 재시도0.
- 호출당600초, 방식별1800초, 전체 paired run 최대10800초(3시간)에서 중단.
  단순히 통과시키려고 기한·batch·정답·모델을 도중에 바꾸지 않는다. 새 설계는 별도 비교다.
- 기존 계정에서 무료임이 확인된 NVIDIA 모델/endpoint만 사용한다. 무료 여부 미확인,
  한도 소진·429·503·계약 오류·기한 도달 시 해당 실행과 후속 전송을 중단하고 실패 기록을 남긴다.
- 유료 전환·충전·다른 유료 모델·Luna·Solar/OpenAI 대체·추가 GLM 호출 없음.
- 과거 A의9회 분류시간은 참고로만 적는다. 과거 A와 새 B의 시간만으로 속도 우열을 정하지 않는다.

## 6. 해석과 채택 기준(검토 후 고정)

총점 없이 다음을 함께 본다. 주 정답을 모두 보류시키는 방식은 채택하지 않는다.

- 주 평가 오확정은 A보다 증가하지 않고 Firefox/Chrome의 오확정은 각 실행에서0.
- linkding/Django/JavaScript/PWA 네 정상 anchor가 B의 세 실행 모두 올바른 필드로 유지되어야 한다.
- 정상 대조 Internet Archive/태그 정리 유지. 정상6개 누락 및 불필요 보류는 A보다 악화하지 않아야 한다.
- 정답 밖 신규 오류/실패가 있으면 '개선 확정'을 보류한다. 어떤 출력도 조용히 평가에서 삭제하지 않는다.
- 호출/시간은 독립적인 비용 수치다. 빨라졌다는 이유로 오확정을 허용하지 않는다.
- 이 1문서는 이미 실패를 관찰한 개발 사례다. 성공하더라도 다른 문서 일반화·운영 적용을 주장하지 않는다.

## 검토 초점

반복 occurrence를 하나의 정답으로 덮는 오류, PWA의 명사구와 설치 동작 혼동,
JavaScript의 실제 프론트엔드 근거를 개발 문단이라는 이유로 버리는 오류,
브라우저 지원을 외부 연동으로 보는 오류, 실패 응답/전부 보류를 품질 개선으로 세는 오류를 확인한다.
