# tentative/proposed 후보 유실 방지 — 오프라인 결과

작성일: 2026-10-03. 큰 Goal은 `paused` 유지.

## 1. 범위와 결론

저장된 실제 모델 응답을 재생해 RelayWave A/B의 `excluded`를 `needs_confirmation`으로 바꿨다. 원시 모델 상태는 두 응답 모두 `tentative/proposed` 그대로이며, 긍정 채택으로 승격하지 않았다. 이번 결과는 **서버의 미정 정보 유실 방지**다. 모델 정확도 개선이나 전체 분석 성공으로 계산하지 않는다.

- 제품 코드 변경은 `ai_service/agentfit_ai/candidate_semantic_assessment.py`의 `_decision` 한 곳이다.
- 새 모델 호출·외부 네트워크 전송·서비스 적용·Spring 저장·사용자 확정: 모두 0.
- 지침 A/B, 모델, 출력 스키마, v2/v3 계약 형식, 검토 정책, 기존 골드: 변경 없음.
- 새 분기에는 제품명·후보 ID·문서 문구 조건이 없다.
- 원본 실행은 `E:/AgentFit/output/role-context-ab-20261003-v1`, 이번 파생 기록은 별도 `E:/AgentFit/output/tentative-proposed-preservation-20261003-v1`에 보존했다.

## 2. 수정 전 재현과 최초 원인

수정 전에 32개 저장 판정을 현재 코드로 재생해 원래 결과와 전부 일치함을 확인했다(`before.json`). D2의 C006이 A/B에서 같은 문제를 보였다.

| 항목 | A/B 공통 저장값 |
|---|---|
| 원문 후보 | `RelayWave` |
| 원문 위치 | `[356, 365)` — Unicode 문자 기준 |
| support | `[347, 401)` |
| 원문 근거 | 이번 릴리스에서 RelayWave 알림 서비스를 연동할지는 검토 중이며, 채택 결정은 아직 없다. |
| field / mentionKind | `external_integrations` / `external_service` |
| modelStatus / commitment | `tentative` / `proposed` |
| scope / time / polarity / role | `target` / `current` / `positive` / `product_fact` |
| 근거·상충 검사 | `groundingValid=true`, `conflictsChecked=true`, `counterEvidence=[]` |
| 기존 서버 처리 | `excluded` |

최초 원인은 모델 응답 이후 `_decision`의 복합 제외 조건에 있던 `commitment != 'adopted'`다. 위 행에서는 다른 제외 조건이 모두 false였고 이 조건만 true였다. 따라서 마지막 `modelStatus` 처리까지 도달하지 못했다.

## 3. 최소 변경과 안전 조건

기존 처리 순서를 유지하고 마지막 commitment 검사만 분리했다.

1. 근거 불량, 후보를 포함하는 support 부재, 상충 검색 미완료, counterEvidence 존재 → 기존대로 보류.
2. 역할 불명·역할/필드 불일치·의미 축 불명 → 기존대로 보류. 명확한 범위 밖 조합의 기존 제외 순서도 유지.
3. 다른 프로젝트·예시, 현재가 아닌 시점, 부정, 비제품 사실, `field=other`, `negated/irrelevant` → 기존대로 제외.
4. 위 검사를 통과한 **역할·필드가 일치하는 `tentative/proposed`**만 보류. 역할 정보가 없는 구형 행은 새 예외 대상이 아니다.
5. 정상 `confirmed/adopted`의 기존 supported 처리는 유지.

부정과 역할 불일치 등 여러 문제가 겹쳐 앞선 안전 검사가 먼저 보류하던 경우도 그대로다. 이번 수정이 부정이라는 이유로 기존 보류를 새로 제외하거나, tentative라는 이유로 모든 검사를 건너뛰지 않는다.

원시 `modelStatus`, 의미 축, `support`, `counterEvidence`와 근거 변환 결과는 동일하다. 별도 서버 `decision`과 그로부터 계산되는 내부 label만 달라진다.

## 4. 같은 저장 응답 32개 비교

각 문서 8개 × A/B 두 응답, 총 32개 판정이다. 합성 문맥에 대해 과거 실제 모델이 생성한 응답을 재생한 것이며, 이번에 모델을 실행한 결과가 아니다.

| 자료 | supported 전→후 | needs_confirmation 전→후 | excluded 전→후 |
|---|---:|---:|---:|
| D1 A | 2→2 | 5→5 | 1→1 |
| D1 B | 5→5 | 0→0 | 3→3 |
| D2 A | 2→2 | 4→5 | 2→1 |
| D2 B | 4→4 | 1→2 | 3→2 |
| 합계 | **13→13** | **10→12** | **9→7** |

변경된 행은 D2 C006 A/B 두 개뿐이다. 나머지 30개 판정 및 전체 32개의 원시 판단은 동일하다. 기존 잘못된 긍정 분류나 `other/confirmed` 오류를 해결했다고 주장하지 않는다. 기존 정상 의미 골드와 품질 점수는 다시 작성하지 않았다.

## 5. 최종 확인 응답 경계

실제 후속 검토 응답이 없으므로 GLM 검토 성공을 만들거나 전체 파이프라인에 저장된 분류를 임의로 주입하지 않았다.

대신 다음 **경계 단독 합성 입력**으로 기존 `project_candidate_profile → project_candidate_confirmation → validate_candidate_confirmation`을 확인했다.

- raw 저장 A/B에서 재검증한 RelayWave 행을 사용.
- `coverage_verified=False`, 전 필드 unresolved인 보수적 envelope.
- 검토 응답을 제공하지 않음. `reviewIssueCount=0`은 검토 완료/통과를 뜻하지 않는다.
- v3의 `reviewDispositions=[]`: 검토 판정을 새로 만들지 않음.
- 이 envelope는 실제 worker가 검토 실패 후 사용자에게 부분 결과를 내보낸다는 뜻이 아니다.

두 계약·두 응답 모두 최종 결과에 다음 정보가 실제로 남았다.

```json
{
  "id": "C006",
  "sourceValue": "RelayWave",
  "documentId": "SYNTHETIC-BOUNDARY-D2",
  "candidate": {"start": 356, "end": 365},
  "support": [{"start": 347, "end": 401}],
  "modelStatus": "tentative",
  "commitment": "proposed",
  "decision": "needs_confirmation"
}
```

- `sourceValue == document[356:365]` 검증 통과.
- `profile.data.external_integrations=null`, 해당 evidence는 빈 배열.
- 해당 `fieldStates`는 `unresolved`; `confirm_external_integrations` 질문 존재.
- 임의의 긍정 Profile 값 및 `user_confirmed` 주입은 검증에서 거부.
- 후보 레코드 수 1→1, 명시 보류 후보 0→1. 질문은 10→10: 모든 필드를 unresolved로 둔 합성 조건의 결과이므로 실제 확인 부담 지표로 일반화하지 않는다.

실제 후속 검토·전체 최종 Profile 결과와 질문 수는 **미측정**이다. 기존 40개 의미의 보존·보류·누락 수치도 이번 경계 검사로 변경하지 않는다.

이 경계 검증은 실제 파이프라인이 unresolved 상태를 전파하는 과정까지 입증하지 않는다. 저장된 후속 검토가 없어 확인 응답을 만드는 함수와 검증기까지만 검사했다.

## 6. 검증 결과

### 이번 원인과 기존 요청 범위

| 검증 | 결과 |
|---|---|
| 수정 전 새 회귀 테스트 | 12개 중 5개 실패 — 저장 A/B·의도한 조건·최종 경계 유실 재현 |
| 수정 후 새 회귀 테스트 | 12/12 통과 |
| 모든 enum 조합 차등 비교 | 99,792개 중 의도한 역할/필드 10개 조합만 제외→보류 |
| 기존 역할 원인 회귀 | 18개: 14 통과, 기존 모델 오류 예상 실패 4개 유지 |
| 따옴표 원문 위치 연결 | 12/12 통과 |
| v3 검토 보류 재생 | 12/12 통과 |
| v3 worker/HTTP/mock 전달 경계 | 6/6 통과 |
| 최종 선택 회귀 합계 | 60개 실행: 56 통과, 예상 실패 4개. 예기치 않은 실패 0 |

해결된 기존 `test_separate_proposed_in_scope_fact_remains_pending`의 `expectedFailure` 표시 한 개만 제거해 필수 성공 회귀로 바꿨다. assertion은 유지했다. 기존 네 개 모델 오류의 기대값은 바꾸지 않았다.

외부 DNS·소켓 차단을 검증한 뒤 테스트를 실행했고, Python 자식에도 차단 경로를 전달했다. 테스트 자식 환경에서 API 키 환경변수를 제거했다. 로컬 HTTP/IPC 테스트의 loopback만 허용했다. 새 회귀는 추가로 provider와 socket 호출을 차단한다.

### 전체 테스트는 완전 통과하지 않음

전체 첫 실행은 **1,500개, 117.662초**였고 `failures=2, errors=9, skipped=7, expected failures=4, unexpected successes=1`이었다.

- 실패 2개와 오류 9개는 모두 기존 `test_review_recovery`에서 현재 코드와 과거 동결 실행 코드가 달라 `CODE_MISMATCH`로 거부된 결과다. 이번 서버 파일 변경에 따른 불일치이며, 수정 전부터 있던 실패라고 단정하지 않는다.
- 복구 검사의 의미는 유지했다. 동결 코드 해시·원본 기록을 갱신하거나 검사를 약화하거나 테스트를 건너뛰지 않았다. 이 11개 복구 시나리오는 새 코드에서 통과한 것으로 보고하지 않는다.
- unexpected success 1개는 위 미정 후보 회귀가 실제로 해결돼 발생했다. 예상 실패 표시 제거 후 해당 18개 회귀를 재실행해 확인했다.
- 기존 skip 7개(심볼릭 링크 환경 1개, 선택 Docling 의존성 6개)는 변경하지 않았다.
- 전체 suite를 재실행해 통과했다고 주장하지 않는다. 후속 검증은 변경된 표시와 요청한 회귀 범위에 한정했다.

전체 로그: `E:/AgentFit/output/tentative-proposed-preservation-20261003-v1/tests-102458265154.txt`.
최종 개별 로그: `tests-103414976017.txt`, `tests-103416827696.txt`, `tests-103412956677.txt`, `tests-103416925600.txt`, `tests-103415460480.txt`.

독립 읽기 전용 리뷰에서 수정이 필요한 코드 결함은 보고되지 않았다. 구 파생 판정의 버전 호환성 및 경계 단독 검증의 한계를 확인했고, 아래와 위 절에 반영했다. 리뷰어의 코드 검토를 추가 테스트 실행으로 계산하지 않았다.

## 7. 원본 보존·버전 호환성 한계

독립 fixture 24개 blob과 보호 파일 208개의 해시를 최종 확인했다. 원본 실행·원시 응답·기대값·B 지침·기존 AgentFit 골드·보호 대상 서비스 계약 파일에 변경이 없었다.

- 수정 전 제품 파일 SHA256: `fdeb5a5b011836daa86f6d5d1e10ac47ad7bd4a9fa7a3269569d5a7d97e24b23`
- 수정 후 제품 파일 SHA256: `d55fe8b811ce7748ed9ed78f972810139f89183d057a3461c317541413ce614a`

기존 `check_decision_records`는 저장된 서버 decision이 현재 계산과 같은지 검사한다. 따라서 구 코드의 D2 `tentative/proposed/excluded` **파생 레코드**는 새 검사기에 그대로 넣으면 `INVALID_SEMANTIC_ASSESSMENT`로 거부된다. D1의 기존 레코드는 그대로 수용됐다. 이는 이번 서버 판정 변경의 소비자 영향이다.

원본 파생 레코드는 유지하고, **원시 응답을 새 코드에서 재검증한 결과만 별도 기록**했다. 구 결과를 새 결과로 덮어쓰거나 코드 버전을 섞어 복구하지 않는다. v2/v3 필드·enum·응답 형식 변경 및 데이터 마이그레이션은 없고, 실제 Spring 저장 자료의 호환성은 미검증이다.

## 8. 변경 파일

- 제품: `ai_service/agentfit_ai/candidate_semantic_assessment.py`
- 테스트: `ai_service/tests/test_tentative_proposed_preservation.py`, `tentative_proposed_fixture.py`, `test_mention_role_cause.py`
- 동결 재생 자료: `ai_service/tests/fixtures/tentative_proposed/`
- 명세·계획·기록: `specs/ai-developer/tentative-proposed-preservation/`
- 오프라인 재현·재생·검증 도구: `work/harness/tentative-proposed-preservation/`

브랜치: `feature/tentative-proposed-preservation` (기준 `3d0bbee`). 외부 네트워크 금지에 따라 push하지 않는다. 원래 작업 중이던 다른 파일은 수정·스테이징 대상에서 제외한다.

## 9. 남은 범위

모델 상태 오류, 프로젝트명·Codex 역할 혼동, 실제 후속 검토 및 전체 모델 실행 결과, 운영 적용, Spring 호환성은 해결했다고 표시하지 않는다. 과거 실행의 복구 hash 검증은 그대로이며 재개·복구 worker 변경도 하지 않았다. 큰 Goal은 일시중지 상태로 종료한다.
