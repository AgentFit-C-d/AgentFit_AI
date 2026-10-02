# LocalSend 실제 비교 결과 — 2026-10-02

## 결론

**전체 비교는 미완료다.** 4번째 요청(DeepSeek 두 번째 배치)에서 첫 실패가 발생해
그대로 중단했다. 실제 호출 총 4회, 재시도 0회, Fluent Reader 호출 0회다.
GLM은 16개, DeepSeek는 8개 후보의 유효 응답만 확보했다. 두 모델의 전체 우열은
판단할 수 없으며, 응답하지 못한 후보를 분류 오답이나 정상 누락으로 취급하지 않는다.

실행 코드: `591965bd0b436371d41f0cef071ec9c250906b3d`.
진단 기반: `f0bdc04`. 요청 전 228개 파일을 동결했고 실행 후 manifest 포함
229개 파일의 동일성을 확인했다. 기존 저장 결과도 보존했다.

## 실제 실패 진단

| 항목 | 관측값 |
|---|---|
| 모델·배치 | DeepSeek v4.1 Flash, LS 배치 2, 호출 순번 4 |
| 처리 시간 | 26.886초 |
| HTTP 상태 | 200 |
| Content-Type | text/event-stream |
| 오류 위치 | sse.event |
| 실패 이벤트 | 첫 번째 data 이벤트, 87바이트 |
| 이벤트 내용 | `{"error":{"message":"Internal server error","type":"internal_server_error","code":500}}` |
| 발췌 | 잘림 없음, 자격 증명 없음 |
| JSON 문법 오류 위치 | null: 오류 객체 자체는 JSON으로 읽혔음 |

관측 가능한 실패 원인은 **HTTP 200 응답 안의 SSE 서버 오류 이벤트**다.
기존 조립기는 `error`가 포함된 이벤트를 `INVALID_RESPONSE`로 거절한다.
분류 결과의 필드·status 또는 인용 검증에 도달하기 전 발생했다.
공급자 내부의 구체적인 장애 원인과 지난 실험 5번 실패의 동일 원인 여부는 미확인이다.
원인/옵션/파서를 추측해 변경하거나 다시 호출하지 않았다.

## 호출 결과

| 순번 | 모델 | 배치 | 결과 | 시간 |
|---|---|---|---|---:|
| 1 | DeepSeek | 1 | 8개 검증 성공 | 35.227초 |
| 2 | GLM | 1 | 8개 검증 성공 | 157.238초 |
| 3 | GLM | 2 | 8개 검증 성공 | 248.121초 |
| 4 | DeepSeek | 2 | INVALID_RESPONSE / SSE 서버 오류 | 26.886초 |

전체 경과 시간은 **467.629초(약 7분 48초)**다. 후보 8개씩 두 요청으로 모델당
문서 한 번을 평가하는 구성이다. 모델당 문서 전체를 두 번 반복한 실험이 아니다.

## 관측된 분류 결과

기존 정답·판정식을 그대로 사용했다. LS15는 주 점수에서 제외한다.
DeepSeek 열은 첫 배치에서 실제 관측한 8개만 집계했으므로 GLM 전체 점수와
동일 분모의 모델 비교로 해석하면 안 된다.

| 지표 | DeepSeek — 8/16개만 관측 | GLM — 16/16개 완료 |
|---|---:|---:|
| 주 점수 대상 중 관측 | 8/15 | 15/15 |
| 모델 자체 오확정 | 1 | 3 |
| 서버 통과 오확정 | 1 | 3 |
| 정상 누락 / 관측 정상 정보 | 0/2 | 0/6 |
| 올바른 제외 / 관측 제외 대상 | 5/6 | 6/9 |
| 보류 (주 점수 / 전체 관측) | 0 / 0 | 0 / 0 |
| 인용 결함 | 0 | 0 |
| 미평가 후보 | 8 | 0 |
| 총 호출 시간 (실패 포함) | 62.113초 | 405.358초 |

오확정 사례:

- DeepSeek: LS11 `Play Store`를 외부 연동/confirmed로 확정.
- GLM: LS05 `REST API`, LS06 `HTTPS`를 기능/confirmed로, LS11 `Play Store`를
  외부 연동/confirmed로 확정. 모두 고정 정답은 other/irrelevant/excluded다.
- 위 오확정은 인용 위치 검증을 통과했다. 정확한 인용과 올바른 의미 분류가
  서로 다른 검증 대상임을 보여주는 관측 결과다.

원본 summary의 불완전 DeepSeek 점수에는 미응답 때문에 `normal_missing=4`가
계산되어 있지만 `comparison_metrics=null`이다. 이는 실제 관측된 누락 4건이라는
뜻이 아니다. 원본 점수 파일은 수정하지 않고, 별도 감사에서 관측된 8개만 세어
위 표에 명시했다.

## LS07·LS15

- **LS07 auto-update:** 두 모델 모두 `features / negated / excluded`.
  원문의 자동 업데이트가 없다는 64번 줄을 근거로 선택했다. 고정 정답과 일치한다.
- **LS15 전송 암호화:** DeepSeek 두 번째 배치는 실패하여 판정/근거 선택을 평가할 수 없다.
  GLM은 `features / confirmed / supported`로 확정하고 142번 줄의 보안 통신 설명만 선택했다.
  **230번 줄의 “Disable encryption on both devices”를 상충 근거로 선택하지 않았다.**
  이 항목은 주 점수 오확정 3건에 추가하지 않았으며, 불확실 항목의 보류·상충 검토
  실패 관측으로 별도 보고한다.

## 보존·검증·범위

- 로컬 테스트: 신규 5개 통과. 전체 1,393개 실행 / 1,386 통과 / 7 skip / 실패 0.
- 실행 전 읽기 전용 독립 검토에서 호출 상한·동결·중단 경로의 중요 문제 없음.
- 4개 저장 요청은 이전 동결 LS 요청과 동일. 유효 응답 24개 판정의 raw field/status 보존 확인.
- 오프라인 사후 감사: 동결 입력과 이전 결과의 해시 264개 확인, 기존 자료 내용 변경 없음.
- 무료 사용 근거는 앞선 사용자 확인과 이번 동일 엔드포인트 4회 승인이다.
  계정 잔여 무료 한도/청구서는 독립 조회하지 않았다. 유료 전환·충전·대체 호출은 하지 않았다.
- 서비스 적용 및 큰 goal 재개 없음. 지침·스키마·정답·서버 판정·옵션 변경 없음.
- 결과 확인 후 튜닝·재호출 없이 종료한다.

## 자료

- [실행 동결](E:/AgentFit/output/localsend-model-comparison-v1/freeze.json)
- [실패 진단](E:/AgentFit/output/localsend-model-comparison-v1/calls/04-finished.json)
- [원본 집계](E:/AgentFit/output/localsend-model-comparison-v1/summary.json)
- [오프라인 감사](E:/AgentFit/output/localsend-model-comparison-v1/audit.json)
- [동결·기존 결과 보존 확인](E:/AgentFit/output/localsend-model-comparison-v1/verification.json)
- [로컬 테스트 로그](E:/AgentFit/output/localsend-model-comparison-preflight-tests.log)
