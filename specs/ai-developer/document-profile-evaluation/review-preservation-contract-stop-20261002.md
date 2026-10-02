# 검토 불일치 후보 보존: 응답 계약 확인 후 구현 중단

## 결론 및 중단 근거

사용자가 승인한 작은 구현을 시작하며 현재 코드와 소비자 경계를 확인했다. **원문 값·위치·검토 거절 이유·검토 후 보류를 분리해서 최종 응답에 남기려면 confirmation-v2 응답 계약 확장이 필요하다.** 사용자 조건2의 “공개 응답 계약 변경이 필요하면 구현을 멈추고 영향과 대안을 보고”를 적용해 제품 코드 수정 전에 중단했다.

여기서 변경이 필요한 계약은 AI의 `/internal/v1/analyze`가 외부 소비자에게 반환하는 HTTP 응답 계약이다. 공개 Spring Profile/OpenAPI 자체가 반드시 바뀐다고 단정하지 않는다. 현재 구현된 AI HTTP 경계와 mock 소비자가 새로운 메타데이터를 거부한다는 사실을 확인했다. 실제 Spring 코드는 제공되지 않아 영향은 미확인이다.

- 기준 코드: `864c4d3162485db0b0aa6ea626319cb45ef42709`.
- 작업 브랜치: `feature/review-disagreement-preservation`.
- 큰 Goal: 실제 상태 `paused` 확인, 재개하지 않음.
- 제품 코드·모델·지침·추출·골드·Spring 저장·서비스 적용 변경0. 새 모델 호출·재시도0.
- 현재 결과는 **수정 전 재현과 계약 사전 검증**이며, 수정 완료나 수정 후 테스트 통과가 아니다.

## 실제 코드에서 확인한 제약

| 위치 | 현재 동작 | 보존 요구에 미치는 영향 |
| --- | --- | --- |
| [candidate_first_profile.py:415](E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service/agentfit_ai/candidate_first_profile.py:415) | wrongCandidateIds를 irrelevant로 전환 | 긍정 Profile에서 제외됨 |
| [candidate_split_review.py:211](E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service/agentfit_ai/candidate_split_review.py:211) | 거절 이유는 선택형 review_reasons 수집기로 전달 가능 | 내부 수집은 가능하지만 현재 최종 응답에 넣을 필드 없음 |
| [candidate_semantic_assessment.py:109](E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service/agentfit_ai/candidate_semantic_assessment.py:109) | modelDecisions 허용 키가 고정되고 decision을 원시 분류 축에서 재계산 | supported만 needs_confirmation으로 덮어쓰면 INVALID_SEMANTIC_ASSESSMENT |
| [candidate_confirmation.py:94](E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service/agentfit_ai/candidate_confirmation.py:94) | 최상위 키와 질문 키·reason 허용 집합이 고정 | 별도 검토 처리/거절 이유 필드와 질문 사유 코드를 거절 |
| [http_service.py:304](E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service/agentfit_ai/http_service.py:304) | 위 검증기를 HTTP 반환 전에 실행 | 합의되지 않은 필드 추가는 INVALID_ANALYSIS_RESULT 경로로 감. 실제 HTTP 요청은 이번에 실행하지 않음 |
| [contract_mock/gateway.py:67](E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service/contract_mock/gateway.py:67), [schema.py:80](E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service/contract_mock/schema.py:80) | 응답과 리뷰 메타데이터 키를 엄격하게 검증 | AI 쪽 키 허용만 풀어도 기존 소비자는 새 메타데이터를 거부함 |

원문 값·위치는 현재 modelDecisions의 sourceValue/candidate/documentId에 이미 남아 있다. 하지만 제외된6개는 decision=supported 상태의 감사 기록일 뿐이고, 검토 거절 이유와 명시 보류 의무는 없다. fieldStates=unresolved와 일반 REVIEW_ISSUE 질문만으로 후보별 보류를 표현했다고 계산하지 않는다.

`counterEvidence`, `groundingValid`, `conflictsChecked`를 거절 사유 저장용으로 바꾸면 실제 분류 사실을 조작하게 된다. `questionId`나 sourceValue에 사유를 끼워 넣는 것도 계약·원문 연결을 훼손한다. 이런 우회는 구현하지 않았다.

## 별도 동결 fixture와 재현

저장 평가의 trace.json/source.md/document.txt/gold.json/result.json/meaning-audit.json/audit-summary.json을 별도 폴더에 바이트 그대로 복사했다. [freeze.json](E:/AgentFit/output/review-disagreement-preservation-preflight-20261002/freeze.json)에 각 SHA-256과 코드 해시를 기록했고 원본/복사본 일치를 검증했다.

실제 모델 transport와 socket 연결을 차단하고 자격 증명을 읽지 않았다. 저장된 GLM 응답23·24·25만 재생했다. 재생 요청의 모델·system·원문·후보·스키마·옵션 전체가 저장 요청과 동일한지 검사했다. 기존 검토 함수, label 적용, 최종 투영, 확인 응답 검증은 실제 함수를 사용했다. 의미 분류 이전 단계를 재실행한 것은 아니다. 그 입력은 고정 trace의145후보·기존 분류다.

재생 최종 응답은 기존 result.json과 완전히 같았다. 따라서 아래 정상 의미 수는 기존 의미 감사와 동일하며 새 판단 기준으로 다시 점수를 올린 것이 아니다.

## 수정 전 테스트 결과

**16개 테스트 메서드 실행: 12개 통과, 4개 메서드 실패(하위 사례 포함 실패5건), 오류0.** 제품 코드 수정 없이 요구사항 실패를 확인한 RED 상태로 멈췄다.

| 검증 | 결과 |
| --- | --- |
| 저장 응답 재생 → 기존 최종 응답 완전 동일 | 통과 |
| R1 재접속 유지·호환 후보 없음의 명시 보류 | 각각 실패. C077/C079가 여전히 supported 감사 기록에만 남음 |
| R2 검토 제외 PDF·Markdown 후보의 명시 보류 | C120/C121 각각 실패. 대체 보류 C042/C043/C119 보존 검사는 통과 |
| R3 중복 정상 의미·역할/업무 애매함 유지 | 기존 대체 값·원시 메타데이터·사람 검토 판정 유지 확인 |
| R4 검토 통과27개 | 모든 긍정 근거 위치와 기존 Profile 동일 |
| R5 미검토112개·기존 확인52개 | label·확인 후보·질문 모두 동일 |
| R6 미해결 문제 분리 | Codex 긍정 오답, 이름 null, 텍스트 anchor 탈락이 그대로임을 확인 |
| 계약 제약5개 | 최상위 검토 필드 추가, modelDecisions 사유 추가, decision 단독 변경, 질문 reason 변경, mock 리뷰 필드 추가 모두 기존 계약에서 거부됨을 확인 |

R3–R6 통과는 **현재 동작의 재현/불변 검사**다. 미구현 수정의 회귀 통과로 표현하지 않는다. 테스트에 쓰인 기존 ID는 fixture 추적용이며 제품 조건 분기에는 추가하지 않았다.

### 별도 합성 오답 사례

원문: `The product does not provide bulk export.` 모델이 bulk export를 긍정 기능으로 잘못 분류했지만 검토가 올바르게 거절하는 고정 응답 사례를 사용했다.

- 잘못된 긍정 기능을 자동 복원하지 않는 검사: **통과**. features=null, 근거=[], 기능 필드는 unresolved.
- 거절된 후보를 명시 보류로 남기는 요구: **실패**. 원시 supported 감사 기록만 남음.
- 기존40개 의미 분모에는 넣지 않았다. 실제 모델의 새로운 판단이 아니며, 수정 후 동작도 아니다.

## 지표 — 수정 전 재현만 존재

| 지표 | 기존 저장 결과 | 현재 코드 재생 | 수정 후 |
| --- | ---: | ---: | --- |
| 정상 의미 보존 | 26 | 26 | 미구현 |
| 정상 의미 보류 | 9 | 9 | 미구현 |
| 정상 의미 누락 | 3 | 3 | 미구현 |
| 사람 검토 필요 | 2 | 2 | 미구현 |
| 최종 긍정 오답 | 1 | 1 | 미구현 |
| 명시 확인 후보 | 52 | 52 | 미구현 |
| 질문 수 | 11 | 11 | 미구현 |

질문11은 필드 질문10 + 미할당 후보 묶음1이다. 긍정 값26개(오답1 포함), 긍정 원문 위치27개, 기존 확인 후보52개는 유실되지 않았다. 재접속 유지·정보 부족/호환 후보 없음의 누락2개는 **아직 해결되지 않았다**. 원문 값·위치는 감사 메타데이터에 있지만 검토 거절 이유와 명시 보류 연결은 최종 응답에 없다.

## 영향과 대안

### A. 검토 처리 메타데이터를 별도 응답 항목으로 추가 — 추천, 아직 미승인

아래는 계약 제안 예시이며 현재 코드가 허용하는 응답이 아니다.

```json
{
  "reviewDispositions": [
    {
      "candidateId": "C077",
      "disposition": "needs_confirmation",
      "reason": "not_product_fact"
    }
  ]
}
```

- 원문 값·위치·documentId는 기존 modelDecisions의 같은 후보에 연결한다. 원시 판단은 변경하지 않고 검토 후 보류를 별도로 표현한다. 사용자의 직접 확정은 이 메타데이터로 생성하지 않는다.
- 검토 거절 후보만 포함하고, 존재/중복/근거 연결/사유 enum/긍정 Profile 재포함 금지를 검증해야 한다. 모든 후보를 보류로 바꾸지 않는다.
- 영향: 검토 사유 전달, 최종 응답 구성·검증, HTTP/프로세스 소비자, mock 리뷰 검증·전달의 호환성 확인이 필요하다. model prompt/schema 변경 없이 가능하지만 **응답 계약은 확장**된다.
- 기존 v2의 엄격한 소비자와 호환되지는 않으므로 새 계약 버전 또는 명시적인 계약 협상이 필요하다. 어느 방식을 쓸지 이번에 임의 결정하지 않았다. 실제 Spring 저장 수정·배포는 이번 범위에서 제외한다.
- 후속 구현의 기대는 정상 누락2개가 보류로 이동하는 것이지 긍정 값 보존·모델 정확도 개선이 아니다. 전후 수치는 실제 수정 후 고정 응답 재생으로 확인해야 한다.

### B. 계약을 그대로 유지하고 내부 감사 자료만 보강

원시 trace의 거절 사유를 내부 기록에 추가 보존하는 것은 가능하다. 하지만 사용자 확인 경로에 명시적인 후보·거절 이유를 전달하지 못하므로 이번 목표를 충족하지 않는다. 내부 기록만 보강하고 완료했다고 보고하는 부분 구현은 하지 않았다.

기존 decision을 재정의하거나 원시 분류 축을 변경해 보류를 강제하는 방식은 원시 판단과 검토 후 처리를 섞으므로 추천하지 않는다.

## 남은 문제와 종료

- 계약 범위 결정 전 제품 코드 수정 중단. 수정 후 R1–R6·합성 회귀 결과는 아직 없음.
- Codex 관계 오분류, 프로젝트명 분류, 텍스트 입력 위치 연결, 실제 처리 시간은 미해결이다.
- 새 모델 호출·운영 서비스 적용·실제 Spring 저장·큰 Goal 재개 없음.
- [재현 결과](E:/AgentFit/output/review-disagreement-preservation-preflight-20261002/preflight-results.json), [재생 최종 응답](E:/AgentFit/output/review-disagreement-preservation-preflight-20261002/replayed-result.json), [검토 사유](E:/AgentFit/output/review-disagreement-preservation-preflight-20261002/replayed-review.json), [실패 상세](E:/AgentFit/output/review-disagreement-preservation-preflight-20261002/failure-details.txt), [오프라인 재현 스크립트](E:/AgentFit/output/review-disagreement-preservation-preflight-20261002/review_preservation_preflight.py).
