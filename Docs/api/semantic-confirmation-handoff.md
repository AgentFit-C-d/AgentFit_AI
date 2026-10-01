# 의미 판단과 사용자 승인 저장 인계

## 검증된 경계 / 미검증 경계

로컬 NVIDIA 후보 경로 → confirmation-v2 → FastAPI HTTP → gateway → in-memory mock → 인증된 사용자 PATCH를 테스트한다. 실제 Spring 저장소·DB·사용자 화면은 제공되지 않아 미검증이다. 공개 `openapi.phase1.json`과 Profile 형식은 변경하지 않았다.

## AI 내부 응답

기존 confirmation-v2의 `outcome=needs_confirmation`, `fieldStates`, `questions`, `profile`에 선택적 `modelDecisions`를 보존한다. 기존 metadata 없는 응답도 허용하지만 모델 판단을 추정해 만들어 저장하지 않는다.

각 결정: 후보 id/문자 위치, 서버가 원문으로 계산한 sourceValue/documentId, field, 모델 원래 `modelStatus`, scope/time/polarity/commitment/role, 상충 검토 여부, 지지·상충 근거 위치, groundingValid, 서버 `decision(supported/needs_confirmation/excluded)`.

- `modelStatus=confirmed`는 모델 주장이다. 사용자 확정이 아니다.
- `decision=supported`는 의미 축·근거 위치의 일관성 조건을 통과한 제안이다. 의미 정확성 보증이나 사용자 승인이 아니다. 후속 검토에서 다시 보류될 수 있다.
- 근거 부족·상충은 해당 필드를 unresolved로 만들고 후보 기록을 보존한다. 공개 Profile에는 미확정 후보를 확정 값으로 넣지 않는다.
- source `DOCUMENT`는 값이 나온 곳이다. 사용자가 문서 값을 그대로 승인해도 source는 DOCUMENT이고 승인 주체는 사용자다.
- 필드를 정하지 못한 확인 대상은 `unassignedQuestions`의 `review_unassigned`와 후보 ID 목록으로 별도 전달한다. 이 목록의 후보를 숨기거나 모든 필드 질문으로 확대하지 않는다. 사용자 화면은 각 후보의 근거와 상태를 보여줘야 한다. 이 목록과 필드 질문을 모두 검토해야 하며, 질문 묶음 수와 실제 후보 수는 별개다.

## Spring 저장 시 구현할 데이터

초안의 모델 판단과 사용자 승인 기록을 별도 테이블/객체로 보관하고, 프로젝트·문서·초안 버전으로 연결해야 한다. mock은 `confirmation_provenance(owner, project)` 내부 조회 메서드로 이 분리를 검증한다. 아직 합의되지 않은 공개 조회 API를 추가하지 않았다.

사용자 승인 기록은 서버 인증 주체, USER_SAVE_PROFILE, 승인 시각, projectVersion, profileVersion, 참조 draft id/version, 분석 완료 당시 source(documentId/attemptId), previousProfileVersion, 승인한 data의 SHA-256, 모델 판단 스냅샷, 필드별 accepted/edited/cleared/manual과 confirmed/unknown을 포함한다. 모델이나 클라이언트가 actor/userConfirmed/modelDecisions를 SaveProfileRequest에 삽입할 수 없다. 승인 이력에도 원문 전체나 API키를 저장하지 않는다. 미분류 모델 질문은 pendingModelQuestions로 남기며 저장 버튼만으로 해당 후보가 확인 완료됐다고 표시하지 않는다.

모델 결정은 일관성 검증 대상이다. 각 Profile 값과 정확한 supported 후보 값·위치를 연결해야 하며, 넓은 evidence span 안에 다른 단어가 있다는 이유로 값을 허용하지 않는다. 병기 프로젝트명은 기존 원문 표현 검증과 unresolved 상태를 함께 요구한다. 저장 단계의 sourceValue는 원문을 가진 AI 경계에서 계산·검증된 값을 전달받는 계약이며, Spring 자체의 원문 재검증·신뢰 경계는 실제 연동 시 별도 확인한다.

새 의미 분류는 현재 `analyze_nvidia_candidates(..., semantic_assessment=True)` 또는 내부 `execute_nvidia_analysis(..., semantic_assessment=True)`에서만 사용한다. 기본 HTTP 분석 경로로 승격하지 않았다. 실제 모델 비교에서 오탐/누락이 남아 실사용 품질 통과를 선언하지 않는다.

## 기존 요청·응답

1. 분석 요청 → DRAFT만 저장. AI가 confirmed라고 해도 CONFIRMED를 만들지 않는다.
2. 사용자가 내용을 확인·수정하고 `PATCH /api/projects/{id}/profile`에 `data`, `expectedVersion`, 선택적 쌍 `draftId`/`draftVersion`을 보낸다.
3. 서버는 소유자·프로젝트 버전·초안 버전을 확인한다. 승인/수정 데이터를 저장하는 같은 트랜잭션에서 사용자 승인 이력을 기록한다.
4. 응답은 기존 `{project, confirmed}`다. 확인 필요 항목의 표시·사용자의 명시적 검토 UI와 추가 승인 의도 계약은 풀스택 연결 시 함께 검증해야 한다. HTTP 요청만으로 사람이 실제 읽었다는 사실까지 증명하지 못한다.

## 실제 연동 검증 항목

- 모델 status와 사용자 승인 컬럼/이력을 혼용하지 않음, 사용자 저장 전 확정 없음.
- 미확정 제안과 지지/상충 근거를 UI에 표시하고 사용자 수정/확인 의도를 저장 요청과 연결.
- 모델 판단 metadata가 HTTP/DB 매핑에서 유실되지 않음.
- 버전 충돌·다른 사용자·가짜 승인 필드 거부. 저장 실패 시 Profile과 승인 이력 함께 rollback.
- 동시 저장 한 건만 성공. 재분석이 확정 Profile이나 과거 사용자 승인 스냅샷을 덮어쓰지 않음.
- 삭제 시 초안·모델 판단·승인 이력·실패 진단 함께 삭제. 실패 원본 7일/접근 제어는 운영 환경에서 별도 검증.
