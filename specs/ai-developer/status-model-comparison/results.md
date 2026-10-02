# DeepSeek / GLM 고정 지침 비교 결과

2026-10-02 KST · 실행 코드 `59fc184` · `feature/status-model-comparison`.

## 결론

**5번째 호출(DeepSeek, LocalSend 첫 배치)의 `INVALID_RESPONSE`로 전체 비교를 중단했다.**
총5회 시도(DeepSeek3/GLM2),응답 검증 완료4회,실패1회,재시도0,미실행3회다.
실제 평가 wall time은412.52초(약6분53초)로 상한90분 이내다.
설정·지침·정답을 바꾸지 않았고 추가 시험·수정·대체 호출은 하지 않았다.

Fluent Reader 16후보는 양쪽 모두 완료했다. 이 문서에서 GLM의 오확정은0건,DeepSeek는2건이었다.
정상10개는 모두 유지했지만 GLM은 명확한 제외 대상4개를 보류해 올바른 제외가1건에 그쳤다.
따라서 오확정 감소와 확인 부담 증가가 함께 관측됐다. LocalSend는 비교할 수 없어
전체32개에서 GLM이 우수하다고 결론내릴 수 없다. 서비스 적용0,큰goal paused 유지 후 종료한다.

## 문서별 비교

오확정·올바른 제외·주 보류는 명확한 정답에 한정한다. FR은 주15개/정상10개/제외5개,
LS는 주15개/정상6개/제외9개다. 모호한 FR16·LS15는 주 점수에서 계속 제외한다.
`—`는 미평가이며0건을 뜻하지 않는다. 누락은 고정 후보의 분류 결과 기준이며 후보 추출 재현율이 아니다.

| 문서 | 모델 | 모델 오확정 | 서버 통과 오확정 | 정상 누락 | 올바른 제외 | 주 보류 | 인용 결함 | 호출/시간 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Fluent Reader | DeepSeek | 2 | 2 | 0/10 | 3/5 | 0/15 | 0/16 | 2회/66.01초 |
| Fluent Reader | GLM | 0 | 0 | 0/10 | 1/5 | 4/15 | 0/16 | 2회/324.12초 |
| LocalSend | DeepSeek | — | — | — | — | — | — | 1회/22.23초,실패 |
| LocalSend | GLM | — | — | — | — | — | — | 0회,미실행 |

FR의 전체 보류(모호항목 포함)는 DeepSeek1/16,GLM5/16이다. 정상 정보 보류는 둘 다0/10이다.
GLM이 모든 후보를 보류한 것은 아니다. 정상 기능·외부 연동·기술 등10개를 두 모델 모두 정확히 보존했다.
FR에서 other/confirmed도 두 모델 모두0건이다.

주 지표는 이번에 새로 호출한 D/G끼리 비교했다. 과거 US 성적을 미완료 문서에 채워 넣지 않았다.
미완료 LS의 내부 score는 미응답 후보를 unassessable로 기록하고 comparison_metrics는null이다.
이를 정상 누락이나 보류0으로 보고하지 않는다.

## FR의 실제 차이

| 사례 | 원문 후보 | DeepSeek field/status → 서버 | GLM field/status → 서버 |
|---|---|---|---|
| FR01 | Windows 10 | other/irrelevant → excluded | deployment/irrelevant → needs_confirmation |
| FR02 | Linux | other/irrelevant → excluded | deployment/irrelevant → needs_confirmation |
| FR03 | A modern UI inspired by Fluent Design System | features/confirmed → supported | features/irrelevant → needs_confirmation |
| FR07 | Google Reader API | external_integrations/confirmed → supported | external_integrations/irrelevant → needs_confirmation |

정답은 네 사례 모두 other/irrelevant/excluded다.
DeepSeek는 외관 설명과 프로토콜을 잘못 확정했다.
GLM은 이들을 confirmed로 반환하지 않았지만,범위 밖 항목에 유효 출력 필드를 붙여 기존 서버 규칙에서 보류됐다.
이 네 건을 올바른 제외로 다시 해석하거나 서버가 자동 제외하도록 바꾸지 않았다.

## FR16·LS15 별도 판정

### FR16 — 추가 RSS 서비스 지원

두 모델 모두 **external_integrations/tentative → needs_confirmation**이었다.
42행 `[2122,2234)`의 추가 지원이 모금 중이라는 문장을 지지 근거로 선택했다.
counterUnitIds는 둘 다 빈 배열이다. 주 점수에 포함하지 않았다.

원문:

> Support for other RSS services are [under fundraising](https://github.com/yang991178/fluent-reader/issues/23).

### LS15 — HTTPS와 암호화 해제 안내

**두 모델 모두 미평가다.** LS15는 LocalSend 두 번째 배치에 속하며 해당 배치가 실행되지 않았다.
따라서 암호화 해제 안내를 상충 근거로 선택했는지는 **확인 불가**다.
미호출을 ‘선택하지 않음’으로 집계하지 않는다.

고정된 검토 문맥은 그대로 보존했다:

- 142행 `[7712,7961)`: HTTPS로 안전하게 전송한다는 주장과 TLS 인증서 설명.
- 230행 `[12922,13127)`: 문제 해결 표의 `Disable encryption on both devices` 안내.

기본 암호화와 선택적 해제의 관계는 사람 검토 대상이다. 정답을 변경하거나 명확한 오답으로 편입하지 않았다.
LS07의 명시적 부정도 첫 LS 배치 실패로 유효 판정을 확보하지 못했다.

## 호출 기록과 처리 시간

| 순서 | 모델 | 문서/배치 | 결과 | 초 |
|---:|---|---|---|---:|
| 1 | GLM | FR/1 | 검증 완료,첫 본 배치로 호환성 확인 | 204.19 |
| 2 | DeepSeek | FR/1 | 검증 완료 | 28.87 |
| 3 | DeepSeek | FR/2 | 검증 완료 | 37.14 |
| 4 | GLM | FR/2 | 검증 완료 | 119.93 |
| 5 | DeepSeek | LS/1 | INVALID_RESPONSE,전체 중단 | 22.23 |
| 6 | GLM | LS/1 | 미실행 | — |
| 7 | GLM | LS/2 | 미실행 | — |
| 8 | DeepSeek | LS/2 | 미실행 | — |

완료된 FR 기준 DeepSeek 평균33.00초/최대37.14초,GLM 평균162.06초/최대204.19초다.
DeepSeek 전체 시도 시간은88.24초(실패 포함),GLM은324.12초다.
서로 다른 수행량인 전체 합으로 속도를 비교하지 않는다. 같은 FR에서 GLM은 약4.9배 시간이 걸렸다.
반복1회분으로 변동성·서버 대기시간과 모델 계산시간을 구분할 수는 없다.

DeepSeek의 FR 사용량은입력26,876/출력1,199토큰이다. GLM은 수신된 조립 응답에 usage가 없어
토큰 사용량 미확인이다. 실패한5번째 호출의 사용량도 미확인이다. 미확인을0으로 계산하지 않았다.

## 실패 발생 지점과 호환성 한계

5번째 호출은 `calls/05-finished.json`에 network_attempted=true,returned=false,
error=INVALID_RESPONSE로 남았다. 기존 NVIDIA SSE transport가 완성된 응답을 반환하기 전 실패했다.
필드 분류나 인용 검증 단계까지 도달한 결과가 아니므로 의미 분류 오답으로 채점할 수 없다.

기존 transport는 SSE를 조립한 응답만 상위 실행기에 전달하며,이번 실패에는 조립 응답이 없어
`05-response.json`도 없다. HTTP 상태/Content-Type/실패 SSE event 원문이 보존되지 않아
어느 수신·검증 조건에서 실패했는지 정확히 특정할 수 없다. 옵션 오류,문맥 길이 문제,
NVIDIA 일시 장애 중 어느 원인인지 추정하지 않는다. 재현 호출과 transport 수정은 하지 않았다.

GLM FR 두 요청의 수용과8개씩의 schema-valid 출력은 확인했다.
그러나 서버 내부 strict schema 적용 및 thinking=false의 실제 효과는 별도 관측 근거가 없다.
모델별 옵션을 빼거나 변경하지 않았으며,기존 공용 GLM 자동 튜닝 경로도 사용하지 않았다.

## 고정·무료 범위·로컬 검증

- 원본 US 지침9,375자,동일 원문·후보±240자·모든 줄단위 ID,정답32개와 기존 server normalizer/score 유지.
  두 모델의 payload는 model만 다르고 stream=true 전송 변환은 양쪽 동일하다.
- 이번 사용자 메시지의 무료 엔드포인트 확인을 새로운 실행 전용 기록으로 보존했다.
  만료된 이전 확인은 재사용하지 않았다. 계정 잔량/청구 화면 독립 조회는 하지 않았다.
  무료 endpoint만 사용,충전/유료 전환/대체 호출0. 요청당600초,이번 작업 종료상한08:10UTC를 적용했다.
- 신규14개 고정 응답 테스트 통과. 최종 전체1376실행/1369통과/7skip/실패0,69.163초.
  고정 응답 테스트 결과와 위 실제5회 호출을 구분한다.
- 독립 검토 Important2건을 재현·수정했다: 선언된 schema 배열 상한 초과 시 중단,
  해시검사/기록 I/O 후 전송 직전 무료 유효성·deadline 재검사. 기존 schema와 판정 규칙은 바꾸지 않았다.
- 사후221개 해시 일치,model 외 요청 차이0,완료된4개 응답의 원시 field/status 보존,
  완료된 문서의 지표 독립 재집계 일치. 새 지침/정답 튜닝0.
- 구현 판단: 기존 GLM 자동 인자 변환을 피하기 위해 동일 parser에 고정 payload 전달 wrapper를 사용했다.
  동일 전송 테스트로 확인했다. 작업 상태는 기존 work/harness에 보존한다. 보류한 minor는 없다.

## 산출물

- 상세 결과: 같은 폴더 `results.json`.
- 전체 원문·후보·정답·8개 예정 요청,실제5개 요청/전송 body,완료4개 응답,
  시작/종료 메타데이터·freeze·summary·verification·postcheck:
  `E:/AgentFit/output/status-model-comparison-v1/`.
- 새 무료 확인: `E:/AgentFit/output/status-model-free-20261002.json`.
- 최종 테스트: `E:/AgentFit/output/status-model-comparison-tests-final.log`.
- 후처리 감사(네트워크 없음): `E:/AgentFit/output/status-model-comparison-postcheck.py`.

전체32개 비교,LS15 상충 근거 처리,계정 quota 독립 확인,옵션 내부 적용,실패 응답 원인은 미검증이다.
이번 부분 결과로 모델 교체나 서비스 적용을 결정하지 않으며 추가 호출 없이 종료한다.
