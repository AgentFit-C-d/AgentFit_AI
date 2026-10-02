# 검토 불일치 후보 보존 — confirmation-v3 오프라인 구현 결과

2026-10-02. 기반 코드 `506a6a0`, 브랜치 `feature/review-disagreement-preservation`.
큰 Goal은 **paused** 유지. 모델·프롬프트·추출·골드·실제 Spring 저장 변경 없음. 새 모델 호출·재시도·서비스 적용·운영 배포 모두 0.

## 구현과 계약 선택

기존 `X-AgentFit-Analysis-Contract` 헤더의 값으로 **confirmation-v3**를 명시 선택한다. 새 옵션 헤더를 만들지 않고 이미 존재하는 버전 검사 경계를 재사용하는 방식이 가장 작다.

- 지원 경로: `integrated-nvidia`의 현재 의미 분류 경로. 기본 v2는 그대로이며 새 필드를 보내지 않는다.
- v3는 `reviewDispositions` 배열을 필수로 전달한다. 검토 거절이 없으면 빈 배열이다.
- 각 항목은 `{candidateId, disposition: "needs_confirmation", reason}`. reason은 기존 검토의 네 코드만 허용한다.
- 후보 ID로 기존 `modelDecisions`의 `sourceValue`, `candidate.start/end`, `documentId`에 연결한다. 원시 판단·support/counterEvidence는 변경하지 않는다.
- 확인 대상은 기존 raw needs_confirmation 후보와 reviewDispositions의 합집합이다. **raw supported/confirmed는 사용자 직접 확정이 아니다.** 검토 이유 역시 모델의 거절 사유이며 의미적 진실을 보증하지 않는다.
- 검토 보류 위치는 긍정 Profile 근거로 사용할 수 없다. 같은 값이 독립 정상 위치에 있으면 허용한다. 괄호 이름 합성으로 보류된 전체 위치를 다시 채택하는 경우도 거부한다.
- 존재하지 않는/중복 후보 ID, 잘못된 상태·사유·추가 키, 원문 값·위치·문서 ID 불일치, 필수 메타데이터 누락, 요청/응답 버전 불일치를 거부한다.
- 미지원 버전·중복 헤더는 분석 전에 거부한다. default 모드의 기존 무헤더·단일 v2 헤더 처리는 유지하고 v3·알 수 없는 버전은 거부한다.

전달 경로:

`기존 검토 사유 수집 → 별도 disposition 생성 → v3 확인 응답 검증 → worker JSON → 자식 프로세스 검증 → /internal/v1/analyze → mock gateway 검증 → 명시 v3 mock 분석 응답의 review`

mock은 `analysis_contract='confirmation-v3'`를 지정한 앱에서만 확장 응답을 전달한다. v2 mock 응답은 기존 형식이다. 실제 Spring OpenAPI·저장 코드는 바꾸지 않았다.

## 고정 자료와 재생 범위

별도 fixture: `ai_service/tests/fixtures/review_preservation/`. 원본 7파일의 정확한 바이트를 gzip으로 보관하고 압축 해제 SHA-256을 검사한다. 원본 평가 폴더는 변경하지 않았다.

| 자료 | SHA-256 |
| --- | --- |
| trace.json | 703d98e7fe11cf50dc59b06c6fb0b053bc8d69d935f97cad541b6e6c8f962158 |
| 원문/document.txt | 9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451 |
| gold.json | 40ecc131c19fb8aa0e0127b67f9a5adf95885ed194a67350d3c89a9e9b328260 |

나머지 result/meaning-audit/audit-summary 및 source 해시는 fixture의 manifest에 보관한다.

- 일반 추출은 저장된 `general_extracted` 객체를 재생한다. LangExtract SDK와 최초 2개의 API 호출을 새로 실행한 테스트가 아니다.
- 이후 저장 요청 3–25의 payload가 원본과 정확히 같은지 검사하고 저장 응답 바이트를 재생한다. operation grounding·분류·검토·투영은 실제 코드로 실행한다.
- AI worker에서 최종 응답까지 v2 재생 결과는 기존 result.json과 전체 JSON 값이 같다. v3도 계약 버전·추가 reviewDispositions 외의 모든 기존 키가 동일하다.
- ASGI 메모리 전달, 자식 stdin/stdout으로 경계를 검사한다. 새 회귀 테스트는 실제 provider 함수와 응용 소켓을 차단한다. Windows asyncio의 내부 socketpair 생성만 런타임 통신을 위해 허용한다.
- **검증 절차 정정:** 초기 전체 회귀에는 기존 합성 loopback TCP 테스트가 섞였다. 부모 소켓 차단으로 일부는 실패했고, 별도 자식에서 실행되는 기존 로컬 TCP 테스트는 실행됐다. 외부 모델 요청은 없었지만 이를 네트워크 전송 0으로 주장하지 않는다. 최종 검증에서는 TCP 테스트 29개를 전부 제외했다. 초기 실행 기록도 삭제하지 않았다.

## 수정 전후 테스트

| 검증 | 결과 |
| --- | --- |
| 최초 보존 테스트 5개 | v2 동일성 1 통과, v3 미구현 4 오류 재현 |
| 경계 테스트 | v3 worker/프로세스/HTTP 전달 미구현 재현 후 수정 |
| mock 최종 전달 | `review`가 빠지는 실패를 재현한 뒤 v3에서만 전달 |
| 독립 리뷰 | default의 미지원 헤더 무시, 괄호 합성의 보류 위치 재사용 2건 발견·수정 |
| 새 회귀 | **18/18 통과**, 독립 리뷰 재실행도 통과 |
| 기존 포함 최종 오프라인 회귀 | **1,392 통과 / 7 skip / 실패·오류 0**. 실행 집계 1,399에 skip 포함 |
| TCP 테스트 | 29개 제외. 선택형 Docling 의존성·Windows symlink 제약으로 7개 skip |
| diff 공백 검사 | 통과 |

전체 회귀 중 기존 CandidateTrace가 호출하던 `_checked_result`의 기본 인자 누락을 발견해 v2 기본값을 복구했다. 초기에 provider 심볼까지 일괄 차단해 기존 함수 동일성·파서 테스트와 충돌한 시험 장치도 수정했다. 제품 동작의 수정과 테스트 장치 보정을 구분한다.

R1–R6 결과:

- **R1:** C077/C079가 원문 연결과 거절 이유를 가진 명시 보류로 남는다. 긍정 자동 복원 없음.
- **R2:** C120/C121도 보류. 기존 대체 후보 C042/C043/C119 불변. PDF·Markdown 의미는 기존에도 보류였으므로 새 의미 회복으로 세지 않는다.
- **R3:** C052/C055를 보류로 전달하며 정상 대체 분석·수정/저장 값 유지. 역할·업무 수집 F06.01은 사람 검토 판정 유지.
- **R4:** 통과한 27개 원문 위치·긍정 값 26개 모두 기존과 동일. Codex 오답도 그대로다.
- **R5:** 미검토 112개 처리, 기존 보류 52개, 원시 판단 145개와 기존 질문이 그대로다. 재분류·일괄 보류 없음.
- **R6:** Codex, 프로젝트명, 텍스트 anchor 문제를 해결 성과로 계산하지 않는다.

별도 합성 사례는 40개 의미 분모에 넣지 않았다. 명시적 부정 원문을 모델이 잘못 supported로 분류하고 검토가 올바르게 거절한 사례에서도 긍정값은 null, raw supported는 감사 기록으로 유지, 검토 후 needs_confirmation은 별도로 전달한다. 동일 값의 독립 정상 후보는 긍정 근거로 유지하되 거절 위치를 추가하면 거부한다.

## 동일 40개 의미 결과

고정된 사람 의미 대응표를 그대로 사용한다. 오프라인 처리 상태의 변화이며 모델 정확도 향상·사용자 승인·저장 성공률로 계산하지 않는다.

| 지표 | 기존 v2 / 수정 전 | 선택 v3 / 수정 후 |
| --- | ---: | ---: |
| 정상 의미: 최종 Profile 보존 | 26 | 26 |
| 정상 의미: 명시 보류 | 9 | 11 |
| 정상 의미: 누락 | 3 | 1 |
| 정상 의미: 사람 검토 필요 | 2 | 2 |
| 최종 긍정 오답 | 1 | 1 |
| 확인 후보 수 (ID 중복 제거) | 52 | 58 |
| 질문 수 (필드10 + 미할당1) | 11 | 11 |
| 원시 modelDecisions | 145 | 145 |

추가 확인 후보는 검토 불일치 6개뿐이다. 질문 수가 같아도 사용자가 확인할 후보는 늘어난다. 실제 UI 확인 부담은 측정하지 않았다.

## 최종 응답의 실제 원문 연결

v3 최종 응답의 `reviewDispositions`와 `modelDecisions`를 후보 ID로 결합해 확인했다. 아래 값은 임의 재작성 없이 최종 응답에서 읽은 내용이다. 위치는 Unicode 문자 기준 `[start, end)`이며 원문 CRLF를 유지한다.

| 의미 | ID / documentId | 원문 위치·값 | 별도 검토 후 상태 / 사유 |
| --- | --- | --- | --- |
| 재접속 후 유지 | C077 / PUBLIC-01 | [3636,3667) — 실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨 | needs_confirmation / not_product_fact |
| 정보 부족·호환 후보 없음 처리 | C079 / PUBLIC-01 | [3745,3786) — 서로 다른 업무·환경에 맞는 결과와 추가 불필요·정보 부족·후보 없음 처리 | needs_confirmation / not_product_fact |

두 후보의 raw `modelStatus=confirmed`, `decision=supported`는 불변이다. 두 위치는 최종 긍정 Profile evidence에 없다. 새 reviewDispositions가 해당 후보의 명시 확인 의무를 표현한다. mock 최종 분석 응답에도 같은 연결이 남고 `confirmed=null`, 직접 확정 이력 `[]`를 확인했다. mock이 생성하는 문서 ID로 연결만 치환한 경계 테스트에서도 원문 값·위치는 그대로다.

최종 재생 산출물: `E:/AgentFit/output/review-preservation-v3-20261002-final/`

- `v2-result.json`, `v3-result.json`: 전체 최종 응답
- `retained-review-evidence.json`: 위 6개의 연결 근거. userConfirmed=false는 감사 결과 표시이며 응답 계약에 추가한 키가 아니다.
- `meaning-comparison.json`: 40개 의미 전후 상태와 고정 원문 근거
- `summary.json`, `test-summary.json`, `unit-tests.txt`: 집계와 전체 테스트 기록

초기 재현·실패 기록은 `review-preservation-v3-20261002`, `review-preservation-v3-20261002-verified` 폴더에 별도로 보존했다. 원본 평가 기록은 덮어쓰지 않았다.

## 변경 파일

| 파일 | 변경 |
| --- | --- |
| agentfit_ai/candidate_review_dispositions.py | 별도 검토 보류 생성·검증, 긍정 근거 배제 |
| agentfit_ai/candidate_analysis_pipeline.py | 명시 선택 시 기존 검토 사유 수집·연결 |
| agentfit_ai/candidate_confirmation.py | v3 생성·검증, v2 기본값 유지 |
| agentfit_ai/candidate_service_worker.py | v3 옵션과 실패/정상 응답 버전 전달 |
| agentfit_ai/analysis_worker.py, analysis_process.py | JSON 요청 버전과 프로세스 출력 검사 |
| agentfit_ai/http_service.py | 기존 헤더의 명시 버전 선택·출력 버전 검사 |
| contract_mock/gateway.py, schema.py, server.py | 선택 v3 검증·최종 review 전달 |
| tests/test_review_preservation.py, test_review_preservation_boundaries.py | R1–R6·합성·불량 연결·전달 회귀 |
| tests/review_preservation_fixture.py, fixtures/review_preservation_worker.py | provider/소켓 차단, 고정 응답·자식 재생 |
| tests/review_preservation_audit.py, fixtures/review_preservation/ | 고정 자료·40의미 감사·오프라인 회귀 도구 |
| 이 보고서, review-preservation-v3-spec.md, work/harness/document-profile-evaluation/STATE.md | 선택 이유·결과·종료 지점 기록 |

위 코드 경로의 기준 디렉터리는 `ai_service/`다.

재현 명령(저장 응답만 사용):

```text
python -X utf8 -m unittest discover -s tests -p test_review_preservation*.py -v
python -X utf8 tests/review_preservation_audit.py OUTPUT_DIR --suite
```

## 남은 문제와 범위

- **미해결:** Codex의 외부 연동 오분류 1건, 프로젝트명 의미 분류, 텍스트 입력 위치 연결 실패, 실제 처리 시간.
- **미검증:** 실제 Spring의 v3 호환성·저장, 운영 배포, 실제 사용자 UI, 다른 문서 일반화, 모델 재실행 정확도/속도.
- mock 즉시 분석 응답까지 검증했다. 기존 mock 상세 재조회 및 이후 직접 저장 감사에 v3 항목을 새로 노출하는 작업은 하지 않았다. 실제 사용자 저장 계약 변경은 후속 범위다.
- 검토 이유의 의미적 정확성을 바꾸는 작업이 아니다. 모델·프롬프트·골드·원시 응답은 보존했다.
- 이 작은 구현·검증 결과에서 종료한다. 큰 Goal은 재개하지 않는다.
