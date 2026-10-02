# Status Model Comparison Plan

> 향후 승인 후 직접 실행은 superpowers:executing-plans를 따른다. 이번에는 계획까지만 작성한다.

**Goal:** 정의 통일 US를 고정하고 DeepSeek V4.1 Flash와 GLM 5.3의 한 쌍을 비교한다.
**Architecture:** 실제 저장 US 요청 4개를 복제하고 GLM 요청의 model만 바꾸는 독립 평가 harness.
기존 unit normalizer·서버 gate·score·특수 사례 진단을 재사용한다. 서비스 import 경로에 연결하지 않는다.
**Tech Stack:** Python/unittest, 기존 NVIDIA SSE transport, SHA-256 입력 고정.
**Spec:** `specs/ai-developer/status-model-comparison/spec.md`.

## Global Constraints

전체32개/주30개/정상16개/제외14개, FR16·LS15 별도 보고. 지침·schema·문맥·정답·서버 판정 고정.
최대8시도, 재시도0, 요청600초, 전체5400초, 동시성1. 만료 무료 기록 재사용0.
관계 검증기·추가 모델 단계·모델별 튜닝·서비스 적용·큰 goal 재개0. 기존 자료 변경0.

## 고정된 입력과 같은 문맥

`input-freeze.json`은 기존 freeze 199개 파일의 해시 확인 결과, 원본 US 요청4개,
원문·32후보·정답·서버 판정 코드·현재 결과의 해시를 기록한다. 실행 승인이나 무료 확인서가 아니다.
`frozen-system.txt`는 03-request.json의 system 9,375자를 복사한 검토용 원본이다.

| 문서/배치 | 원본 저장 요청 | user 문자 수 | 기존 DeepSeek prompt tokens |
|---|---|---:|---:|
| FR/1 | 03-request.json | 31,319 | 13,418 |
| FR/2 | 04-request.json | 32,271 | 13,458 |
| LS/1 | 05-request.json | 86,725 | 35,532 |
| LS/2 | 06-request.json | 87,397 | 35,964 |

양쪽 모두 동일한 전체 원문(FR3,612자/LS14,279자), 후보의 기존 위치·앞뒤240자,
모든 sourceRegistry 줄 단위(FR84/LS305)를 제공한다. 동일 배치의 messages 문자열과 schema를
직렬화 순서까지 비교한다. GLM 문맥이 부족해도 원문을 자르지 않는다. 문자 수를 GLM 토큰 수로 간주하지 않는다.

생성 설정은 기존 temperature0/max_tokens8192/chat_template_kwargs.thinking=false 유지.
저장 payload의 stream=false는 기존 transport가 HTTP body에서 true로 바꾼다.
이 변환을 양쪽에 동일하게 적용하고 비밀 header를 제외한 wire payload도 기록한다.
원본 SSE가 아닌 기존 transport 조립 응답을 저장했다면 그 사실을 명시하고 raw field/status를 보존한다.

## Review Focus

1. US 대신 UC 사용·모델별 지침 추가: 저장 US 요청과 model 외 차이0 검사.
2. GLM의 schema/추론 옵션을 무시한 성공처럼 보이는 응답: 호환성 증거와 내용 검증을 구분.
3. 만료된 과거 무료 기록·실패 후 재실행: 시작 전/각 호출 전 새 근거 검사 및 영구 실행 마커.
4. LS15의 아무 counter를 정답 근거로 간주:230행 실제 위치 포함 여부와 보류 상태를 따로 검사.
5. 모든 후보 보류·부정 삭제로 지표 개선: 정상16개, 제외14개, LS07, 모호2개 별도 분모 고정.

## Task 1 — 승인 후에만: 실행 조건과 로컬 검증

예정 Create: `work/harness/status-model-comparison/{experiment.py,evaluate.py}`,
`ai_service/tests/test_status_model_comparison.py`. 이번에 만들지 않는다.
기존 평가기·서비스 파일은 읽어 재사용하며 변경하지 않는다.

- [ ] 별도 실행 승인과 새 계정 무료 확인을 받는다. 두 모델/endpoint/8시도/출력8192 및 실제 입력 범위를
  포함해야 한다. 기존 무료 JSON의 expires_at만 늘리거나 복사해서 승인으로 쓰지 않는다.
- [ ] `model-check.md`의 schema와 추론 끄기 호환성을 공식 자료로 보강하거나,
  첫 GLM 본 배치를 호환성 검사로 사용하는 승인을 확인한다. 이후 임의 옵션 조정은 허용하지 않는다.
- [ ] `build_model_pair(saved_package: dict) -> dict`: 실제 US 요청4개 검증 후 D/G8개 job 생성.
  G 요청은 model만 교체. gold·이전 결과를 messages에 넣지 않는 테스트부터 작성한다.
- [ ] 기존 EightCallGate의 MODEL 상수 검사와 sender의 응답 모델 검사를 job별 expected model에
  대응하는 새 독립 wrapper로 만든다. 기존 함수 monkey patch·기존 freeze 파일 수정 금지.
- [ ] 고정 응답 테스트: 양쪽 요청 동일성, 원문/후보/32정답 보존, strict schema 순서,
  model alias 불일치 중단, 9번째 호출 차단, timeout/429/402/파싱 실패 후 추가 전송0,
  만료/변조 시 전송0, 실행 마커 재진입 차단.
- [ ] 진단 테스트: LS07 field/negated 보존, FR16/LS15 주 점수 제외,
  LS15 counter 빈배열/다른줄/230행 대조, 전부 보류 시 오확정0이어도 정상누락16 및 올바른제외0.
- [ ] `rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_status_model_comparison.py -v`
  를 `ai_service`에서 실행. 기존 status·classification 테스트도 통과해야 한다.
  고정 응답 테스트를 실제 모델 의미 성능으로 보고하지 않는다.
- [ ] 새 실행 디렉터리에 요청·지침·schema·입력·정답·진단/transport 코드·새 무료 근거를 freeze.
  기존 `status-definition-v1` 결과를 덮어쓰지 않는다. 구현 검토 후 한 번만 실행한다.

## Task 2 — 승인 후에만: 한 쌍, 최대8회

| 순서 | 모델 | 문서/배치 |
|---:|---|---|
| 1 | GLM | FR/1 — 호환성 검사도 겸함 |
| 2 | DeepSeek | FR/1 |
| 3 | DeepSeek | FR/2 |
| 4 | GLM | FR/2 |
| 5 | DeepSeek | LS/1 |
| 6 | GLM | LS/1 |
| 7 | GLM | LS/2 |
| 8 | DeepSeek | LS/2 |

- [ ] 호출 시작 시도부터 누적하고 재시도0. 추가 dry run·모델 목록 조회용 추론·워밍업 호출0.
- [ ] 실제 전송/반환 model·finish_reason·usage·원시 응답·파싱·서버 판정·시간을 순서대로 보존한다.
  600초 요청 제한에는 DNS/큐/SSE 수신을 포함한다. 전체5400초가 지나면 진행 중 요청도 중단한다.
- [ ] 계약/무료/호출 실패 시 즉시 전체 중단, 실패·미실행 후보를 분리한다.
  부분 성공 문서만 골라 전체32개 비교라고 보고하지 않는다.
- [ ] 입력 해시 사후 확인, 후보별 근거와 원시 field/status가 판정 과정에서 변하지 않았는지 확인한다.

## Task 3 — 결과 보고 후 종료

`score_instruction_rows`와 `status-definition-unification/experiment.py:diagnostics`를 그대로 사용한다.

| 지표 | 고정 정의와 분모 |
|---|---|
| 모델 오확정 | 명확30개 중 유효 필드/confirmed이며 기대 field/status와 다른 건수 |
| 서버 통과 오확정 | 위 오확정 중 verdict=supported 건수. 사용자 확정/DB저장을 뜻하지 않음 |
| 정상 누락 | 정상16개 중 올바른 field/confirmed/supported로 남지 못한 건수. raw 누락도 별도 |
| 올바른 제외 | 제외정답14개 중 기대 field/status 일치 및 excluded. 범위밖13/부정1 분리 |
| 보류 | 명확30개·정상16개·모호2개·전체32개 각각의 needs_confirmation 건수 |
| 불확실성 보존 | FR16·LS15 각각 tentative 여부, 실제 verdict, 근거. 확정/제외는 별도 표시 |
| 상충 가능 근거 | LS15 지지142행[7712,7961), 검토230행[12922,13127)의 support/counter 선택 여부 각각 |
| 부정 | LS07 features/negated/excluded 및64행[2598,2733) 유지 여부 |
| 기타 | other/confirmed, 인용결함/평가불가, 후보32보존, 실제시도/실패/미실행, 지연·사용토큰 |

- [ ] FR/LS 각각과 합계를 동일 분모로 작성. 모델·서버 오확정은 따로 유지한다.
  호출별 소요, 문서별 합, 모델별 합, 전체 wall time을 구분하고 평균/최대도 표시한다.
- [ ] FR16의 모금/계획 근거와 LS15의 두 줄을 원문 그대로 나란히 제시한다.
  LS15는 기본 암호화/선택적 해제의 관계가 사람 검토 대상임을 유지한다.
  단순 counter 비어있지 않음 또는 원시 후보 보존을 불확실성 처리 성공으로 인정하지 않는다.
- [ ] **새 D vs 새 G**가 주 비교다. 과거 US(오확정3, 정상누락0, 올바른제외11,
  모호보류1/2, 상충230행 선택0)는 역사적 참고로만 별도 표시한다.
- [ ] 오확정 감소와 함께 정상누락·정상보류가 늘었는지, 올바른제외·모호보류가 줄었는지 보고한다.
  모든 지표를 하나의 점수로 합치거나 결과를 보고 정답·지침을 바꾸지 않는다.
- [ ] 호출1쌍의 한계, 옵션 동등성 미확인 여부, 서버 버전/토큰화 차이를 명시한다.
  결과와 feature 브랜치를 보존하고 종료. 추가 반복/서비스 적용은 별도 판단이다.

## 현재 중단 지점

계획과 입력 고정만 완료. 실제 호출0, 실행기 수정0, 새 무료 확인0.
다음 실행에는 **새 무료 근거 + 명시적 실행 승인 + 호환성 확인/검사 승인**이 필요하다.
