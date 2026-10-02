# AgentFit confirmation-v3 단일 실제 평가 — 첫 검토 요청 실패

## 1. 결과와 종료 상태

승인한 전체 경로 평가를 새로 **1회** 실행했다. DeepSeek 추출·의미 분류까지 완료한 뒤 **첫 GLM 검토 요청에서 PROVIDER_UNAVAILABLE**로 실패했다. 재시도나 후속 호출 없이 종료했다.

- 실행 코드: `9385e22d39494165e5f0b841ea6d611a7435973b`
- 모드: integrated-nvidia / nvidia_only=True / confirmation-v3 명시
- 실제 요청: **24회** = DeepSeek 23회 성공 + GLM 1회 실패
- 실제 전체 시간: **1724.336초(28분44초)**
- 첫 실패 단계: **COVERAGE_REVIEW_FAILED**, 기능 후보 첫 20개 묶음 검토
- 재시도0, 실패 후 호출0, 유료 대체0, 추가 실험0
- 큰 Goal paused. 배포·사용자 확정·Spring 저장·서비스 적용 없음.

이번에는 최종 Profile을 만들지 못했다. 따라서 40개 의미의 최종 보존·명시 보류·누락·사람 검토 필요, 최종 긍정 오답, 최종 확인 후보·질문 수는 **모두 미측정(null)**이다. 미실행 의미를 정답이나 누락으로 계산하지 않았다.

## 2. 허용된 최소 수정과 로컬 gate

제품 분석 패키지 `agentfit_ai`는 이번 작업에서 변경하지 않았다. 모델·프롬프트·모델 스키마·골드·서비스 응답 계약도 그대로다.

- `diagnostic_tools/document_profile_worker.py`: 서비스의 v2/v3만 허용하고 원래 raw 요청을 worker에 전달한다. 계약 생략은 기존 v2, 잘못된 버전·타입과 별도 reviewModel은 계속 거절한다.
- `diagnostic_tools/candidate_trace.py`: 관측 결과 검증에 선택한 계약을 전달한다. 기존 서비스 검증기를 재사용하고 v3 정보를 제거하거나 v2로 가장하지 않는다.
- `diagnostic_tools/document_profile_live.py`: 기존 analysis_process를 사용하며 v3/NVIDIA 단독을 명시한다. 단일 분석 자식에서 기존 inline SSE 전송·해석을 사용하고 부모가 기한을 감시한다. 모델 프롬프트나 의미 분류기를 대체하지 않는다.

실행 상한은 50회/전체1800초/단일600초/재시도0이다. 전체10초를 종료·기록에 남기고, 각 요청은 남은 분석 시간보다 최소2초 짧게 제한한다. 첫 실패 및 동결 위반을 감지하면 이후 전송을 차단한다. 요청 시작 전 제한된 본문과 checkpoint를 저장한다. 부모 감시용 기록은 수정되지 않는 개별 파일로 발행해 Windows의 읽기/교체 잠금 충돌을 피한다.

검증:

- 계약 관측3 + 실행기7 = 관련 **10건 통과**.
- 기본/명시v2의 기존 결과 동일, v3 원시 응답과 검토 보류6개 최종 trace 보존, 미지원 계약 거부 확인.
- 50회 상한, 600초, 남은 시간보다 짧은 제한, 만료 후 시작 금지, 첫 실패 후 전송 금지, 동결 원문을 복원해도 전송 금지 확인.
- 짧은 실제 자식 프로세스로 요청별·전체 만료 시험: 진행 중 프로세스 종료/회수, Windows PID 종료, checkpoint·진단 보존 확인. 외부 통신 없음.
- 최종 전체 offline **1421건 중1414통과/7skip/실패0**, TCP29건 제외. skip은 선택 Docling 의존성6·Windows symlink1.
- 독립 리뷰에서도10/10통과, 실제 평가를 막는 발견 사항 없음.

최초 RED와 Windows journal 교체 오류 기록은 별도 로컬 폴더에 보존했다. 테스트용 저장 응답·후보는 실제 평가 입력에 사용하지 않았다. 실제 요청 종료 시험은 로컬 자식과 연결 종료까지 검증하며, 제공자 서버 내부 추론 취소를 보장하지 않는다.

## 3. 동결과 자료 보존

실행 폴더: `E:/AgentFit/output/document-profile-v3-live-20261002-v1`

- 실제 작업 파일147개 해시와 사본: `freeze.json`, `code-snapshot/`
- Git SHA와 dirty 목록, Python 실행 파일 해시·버전·패키지 버전 기록. LangExtract1.7.0.
- 원문: `source.md`, `document.txt`; SHA `9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451`
- 골드: `gold.json`; SHA `40ecc131c19fb8aa0e0127b67f9a5adf95885ed194a67350d3c89a9e9b328260`
- 실행 전 이전 실제 평가의 원문/골드 해시와 대조했고, 실제 요청에는 원문만 넣었다. 요청24의 document도 원본 CRLF 포함 정확히 동일했다.
- `trace.json`: 요청24개, 성공 응답23개, 완료된 추출·분류와 실패 최종 응답. observationErrors=[]이고 trace 상태는 partial이다.
- `request-journal.json`, 수정되지 않는 `deadline-*.json`, `active-request.json`, `trace-checkpoint.json`, `call-metadata.json`, `execution.json`, `result.json` 보존.
- 실행 후 `integrity-after.json` 및 `report-verification.json`: 코드·원문·골드 불변, API 키 저장 일치0, 실패 후 추가 호출 없음 확인.

키와 인증 헤더는 요청 기록에 포함하지 않았다. 실패 응답 본문을 받은 것처럼 보충하지 않았다. 원문 위치 감사는 `read_bytes().decode('utf-8')`로 CRLF186개를 보존해 수행했다.

보고용 파생 자료: failure-audit-summary.json, focus-candidates-intermediate.json, text-input-intermediate.json, profile-fields-unmeasured.json. 원본 trace와 골드는 수정하지 않았다.

`request-controls-comparison.json`에서 이전·이번 실행의 일반 추출2건, 동작 추출, 첫 분류, 첫 검토 요청을 대조했다. 시스템 지침과 모델·출력 상한·추론 옵션은 동일하다. 검토 스키마의 후보 ID enum만 새로 추출된 후보에 따라 달랐으며, 필드·타입·분류 기준의 변경은 없었다. 새 후보를 기존 ID로 강제하지 않았다.

## 4. 첫 실패의 확인된 진단

| 항목 | 기록 |
|---|---|
| 요청 번호 / 모델 | 24 / z-ai/glm-5.3 |
| 단계 / 대상 | COVERAGE_REVIEW_FAILED / features 후보20개 |
| 적용된 요청 제한 | 365.994초 |
| 요청 메타데이터 소요 | 302.263초 |
| 오류 | PROVIDER_UNAVAILABLE |
| transport_completed | false |
| retry_of_call_index | null |
| response / responseDiagnostic | null / null |

이 요청은 기한을 넘기기 전에 제공자 오류로 끝났다. 이번 실제 실행에서 타임아웃 강제 종료가 발생한 것은 아니다. 타이머 동작은 앞의 로컬 시험 결과다.

현재 전송기는 HTTP500 이상을 PROVIDER_UNAVAILABLE로 매핑한다. 저장된 정확한 HTTP 상태 번호·Content-Type·오류 본문·실패 SSE 이벤트는 없으므로 **503으로 단정하거나 특정 서버 내부 원인을 추정하지 않는다.** INVALID_RESPONSE가 아닌 이번 오류에 상세 응답 진단은 생성되지 않았다. 해당 진단을 추가하기 위한 코드 수정이나 재호출은 하지 않았다.

## 5. 이전 실제 실행과 단계별 비교

시간은 두 실행의 동일한 call-metadata elapsed_ms 합계다. 관측 기록 포함 범위가 다른 trace 응답 타이머와 혼용하지 않는다.

| 단계 | 이전 실제 v2: 호출/초 | 이번 실제 v3: 호출/초 | 이번 완료 범위 |
|---|---:|---:|---|
| 일반 후보 추출 | 2 / 81.279 | 2 / 97.592 | 완료 |
| 동작 후보 추출 | 1 / 106.679 | 1 / 250.668 | 완료 |
| 의미 분류 | 19 / 804.278 | 20 / 1072.452 | 완료 |
| 의미 검토 | 3 / 768.565 | 1 / 302.263 | 첫 요청 실패 |
| 기능 정리·최종 투영 | 별도 모델 호출0, 최종값 생성 | 실행되지 않음 | 미측정 |
| 전체 벽시계 | 25회 / 1762.135초 | 24회 / 1724.336초 | 서로 완료 범위가 다름 |

| 후보 수 | 이전 실제 | 이번 실제 |
|---|---:|---:|
| 일반 추출 객체 | 61 | 63 |
| 일반 추출의 원문 연결 후보 | 103 | 112 |
| 동작 추출 mentions | 57 | 60 |
| 동작 후보 원문 연결 / 거절 | 42 / 15 | 44 / 16 |
| 합쳐진 분류 대상 | 145 | 156 |

이번 분류 단계에서는 supported44, needs_confirmation35, excluded77이 기록됐다. supported44는 기능 후보42 + 외부 연동 후보2다. **42는 최종 기능 문자열 수나 정상 기능36개 의미의 보존 수가 아니다. 35도 최종 사용자 확인 후보 수가 아니다.**

## 6. 40개 의미와 확인 부담 — 실제 실행과 오프라인 재생 구분

| 지표 | 이전 실제 v2 | 이전 v3 오프라인 재생 | 이번 실제 v3 |
|---|---:|---:|---|
| 보존 | 26 | 26 | 미측정 |
| 명시 보류 | 9 | 11 | 미측정 |
| 누락 | 3 | 1 | 미측정 |
| 사람 검토 필요 | 2 | 2 | 미측정 |
| 최종 긍정 오답 | 1 | 1 | 미측정 |
| 최종 확인 후보 | 52 | 58 | 미측정 |
| 질문 | 11 | 11 | 미측정 |

이번의 사람 검토 필요도 2나40으로 임의 입력하지 않았다. 전체 결과가 없는 것이므로 모든 최종 점수는 null이다. 이전 v3 재생은 동결된 이전 후보에 대한 계약 보존 검사였으며 새 모델 실행이 아니다.

코드 두 수정과 모델 응답 변동이 함께 있다. 후보 수·시간 변화 전체를 따옴표 복구 또는 v3 보류 한 수정의 효과로 귀속하지 않는다. 이번 총시간은 검토 실패까지의 시간으로, 완주 속도나 정확도 개선을 입증하지 않는다.

## 7. 주요 후보 추적 — 검토 전 기록

### 텍스트 입력

- 이번 operation mention23: quote=`PDF · Markdown · 텍스트 입력`, anchor=`B`.
- 원문에는 Unicode `[1890,1913)`에 같은 값이 있다. 그러나 `B`는 후보 값을 포함하는 근거 문맥이 아니므로 ambiguous_anchor로 거절됐다.
- 일반 추출의 해당 위치에는 C046=`PDF` `[1890,1893)`, C047=`Markdown` `[1896,1904)`만 있다.
- 이전의 곡선/ASCII 따옴표 차이와 다른 새 모델 응답이다. 제한된 따옴표 복구가 이 anchor를 임의로 연결하지 않은 것은 설정한 보수적 조건과 일치한다.
- 첫 손실 위치는 **원문 위치 연결**. 이번 텍스트 입력의 후속 분류·검토·최종 의미 보존은 검증하지 못했다. 기존40의미의 누락0을 주장하지 않는다.

### 재접속 유지

- C085, `[3636,3667)`: `실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨`
- features / modelStatus=confirmed / decision=supported. 같은 원문 위치를 support로 가진다.
- 분류 단계까지 보존됐지만 검토 응답과 최종 Profile/v3 확인 응답은 없어 최종 상태는 미측정이다.

### 정보 부족·후보 없음 처리

- C088, `[3745,3786)`: `서로 다른 업무·환경에 맞는 결과와 추가 불필요·정보 부족·후보 없음 처리`
- support=`[3671,3788)`의 원문 기능 표, features / confirmed / supported.
- 이 중간 후보를 근거로 후속 안내까지 포함하는 복합 의미 전체의 최종 보존을 확정하지 않는다. 최종 값 또는 v3 확인 후보에 남는지는 미측정이다.

### AgentFit 프로젝트명

- C000 `[2,10)`, C003 `[168,176)`은 project_name / confirmed지만 mentionKind=external_service라 서버 decision=needs_confirmation이다.
- C145 `[7266,7274)`도 project_name / confirmed지만 mentionKind=product_operation이고 needs_confirmation이다.
- field가 맞아도 역할 분류와 충돌하는 문제가 **의미 분류 단계**에 남아 있다. 사용자 직접 확정으로 처리하지 않았으며 최종 프로젝트명은 미생성이다.

### Codex

- C091 `[4020,4025)`: `Codex`.
- 원문 support `[4006,4067)`은 초기 지원 Client 및 Catalog 설명이다.
- 모델은 external_service / external_integrations / confirmed, 서버는 supported로 분류했다.
- 골드에서 Codex는 지원 Client이므로 **분류 단계의 기존 오분류가 다시 관측됐다**. 검토 실패로 이것이 최종 긍정 값에 통과했는지는 미측정이다. 전체 후보의 오답 총수를1로 확정한 것은 아니다.

## 8. 10개 Profile 필드

| 필드 | 고정 기대값 | 이번 실제 최종 값·상태 |
|---|---|---|
| project_name | AgentFit | 미생성·미측정 |
| project_type | 웹 서비스 | 미생성·미측정 |
| domain | AI 개발 도구와 설정 | 미생성·미측정 |
| frontend | 미기재(null) | 미생성·미측정 |
| backend | 미기재(null) | 미생성·미측정 |
| ai | 운영 채택 미정(null) | 미생성·미측정 |
| database | 엔진 미기재(null) | 미생성·미측정 |
| deployment | 환경 미기재(null) | 미생성·미측정 |
| features | 16개 대표 묶음의 세부36의미 | 미생성·미측정 |
| external_integrations | GitHub | 미생성·미측정 |

실제 최종 반환은 `{contract: confirmation-v3, outcome: failed, error: PROVIDER_UNAVAILABLE}`다. Profile의 null과 Profile 자체가 생성되지 않은 것을 구분한다.

## 종료

원문 연결/역할 분류의 남은 문제와 제공자 오류를 기록했으며, 자동 수정하지 않았다. 모델 호출·추가 실험·서비스 적용·사용자 확정·Spring 저장 없이 결과 보고로 종료한다. 큰 Goal은 계속 일시중지다.
