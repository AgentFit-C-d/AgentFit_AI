# 권한·설정 Preview·승인·다운로드 API 초안

> 2026-09-08 · DESIGN DRAFT · 후속 Feature 설계용. 아직 구현하거나 동작을 검증한 API가 아니다.

[공통 PRD](../PRD.md)의 권한·Preview·설정 보관 원칙을 연결하기 위한 초안이다.
첫 문서 분석 흐름을 완료한 뒤 B가 상세 계약을 작성하고 A·Frontend·Designer가 함께 확인한다.
아래 경로·DTO·한도·만료 시간은 후속 Spec·Plan에서 확정할 제안이다.

## 1. 공개 API 범위

모든 API는 로그인과 프로젝트 소유권을 검사한다. 변경 요청은 Origin 검사를 추가한다.
공통 오류 envelope·no-store·시간·식별자 규칙은 [공통 규칙](common.md)을 따른다.

| Method / path | 용도 | 성공 | 주 담당 |
| --- | --- | --- | --- |
| POST /api/projects/{projectId}/config-previews | 선택·권한·기존 설정을 검증하고 미리보기 | 201 { preview } | B, A 저장·접근 제어 |
| POST /api/projects/{projectId}/config-approvals | 표시한 내용에 대한 최종 승인 기록 | 201 { approval } | B·A |
| POST /api/projects/{projectId}/config-exports | 승인한 파일 내용으로 ZIP 생성 | 200 application/zip | B·A |
| GET /api/projects/{projectId}/configuration-history | 최소 생성 이력·근거 조회 | 200 { items, nextCursor } | A·B |
| POST /api/projects/{projectId}/configuration-history/{configurationId}/reports | 사용자의 적용 결과 진술 기록 | 201 { report } | A·B |

MVP 필수는 다운로드와 적용·인증·무해한 사용 확인 안내다.
임의 명령 실행·외부 도구 호출·Secret 저장·사용자 PC 원격 변경 endpoint를 추가하지 않는다.
브라우저 폴더 적용은 선택 기능이며 지원 브라우저의 로컬 사용자 승인과 실제 파일 재확인이 필요하다.

## 2. 세 가지 권한과 승인

| 구분 | 이 API가 보장할 수 있는 범위 |
| --- | --- |
| AgentFit 자체 권한 | 세션·소유권·대상·선택·승인 검사로 서버 작업을 통제 |
| 생성할 Client 정책 | 검사한 Client/도구 버전의 변환 규칙으로 파일에 반영한 정책 |
| 외부 도구의 실제 실행 권한 | 외부 인증·상위 정책·실제 환경 검사 없이는 보장하지 않음 |

선택 전 외부 연결·쓰기·실행 가능한 구성은 비활성이다.
사용자가 선택한 지원 작업의 기본 정책은 ASK_EACH_TIME이며 ALWAYS_ALLOW는 검증된 변환이 있을 때 별도 선택한다.
Client가 매번 물어보는 정책을 선택하는 행위와 이번 설정 파일을 다운로드하도록 승인하는 행위는 서로 다르다.
DENY인 필수 작업을 필요로 하는 도구는 제외해야 한다. 서버가 거부를 임의의 허용으로 바꾸지 않는다.

## 3. Preview 요청

`PreviewInput`은 다음 필드를 모두 받는다. 추가 필드는 거부한다.

```json
{
  "recommendationId": "rec_example_01",
  "expectedBasis": {
    "projectVersion": 1,
    "developerVersion": 1,
    "environmentVersion": 1,
    "catalogRevision": "catalog_example_01"
  },
  "selectedToolIds": ["tool_example_01"],
  "permissionPolicies": [
    {
      "catalogItemId": "tool_example_01",
      "key": "external_service.connect",
      "resourceScope": "service:example",
      "policy": "ASK_EACH_TIME",
      "mappingId": "mapping_example_01"
    }
  ],
  "existingState": "UNKNOWN",
  "existingFiles": []
}
```

ID·scope는 형식 설명용 합성 예시다. 실제로 검증된 Catalog·지원 조합·매핑이 없으면 이 요청은 성공하지 않는다.

| 필드 | 타입·조건 |
| --- | --- |
| recommendationId | 현재 프로젝트의 CURRENT·RECOMMENDED 추천 ID |
| expectedBasis | 서버의 현재 Project.version·Developer/Environment 버전·Catalog revision과 일치 |
| selectedToolIds | 추천에 포함된 배포 단위 ID의 중복 없는 배열, 1–20개 제안 |
| permissionPolicies | { catalogItemId, key, resourceScope, policy, mappingId }[]; 최대 200개 제안 |
| policy | ALWAYS_ALLOW / ASK_EACH_TIME / DENY. 추천이 제공한 해당 매핑의 supportedPolicies 중 선택 |
| existingState | UNKNOWN / USER_SAYS_EMPTY / PROVIDED |
| existingFiles | { targetKey, relativePath, content }[]; 최대 20개 제안 |

- policy의 도구·작업·대상·매핑 조합은 서버가 Catalog와 재대조한다. 누락·중복·임의 scope·미지원 정책은 422다.
- selectedToolIds는 배포 단위 기준이다. Plugin의 포함 컴포넌트·의존 도구를 중복 설치하지 않는다. 필수 의존성이 선택에서 빠지면 해결할 항목을 반환하고 사용자에게 다시 선택하게 한다.
- existingState=PROVIDED이면 existingFiles가 하나 이상이다. 나머지 상태는 빈 배열이어야 한다.
- targetKey와 relativePath는 선택 도구의 검토된 Client 템플릿이 허용하는 대상만 받는다. 절대 경로·상위 경로 이동·NUL·임의 URL·임의 명령을 받지 않는다.
- content는 UTF-8로 다룬다. 이 요청과 export 요청에 한해 JSON body **1 MiB(1,048,576 bytes)**, 파일별 **100,000 code points**를 제안한다. 둘 중 하나라도 넘으면 413이며 자르지 않는다.
- 식별자는 1–128자, 그 밖의 scope·path·key 문자열은 최대 200 code points다. 민감 입력 검사를 저장·로그·외부 전송보다 먼저 수행한다.
- 기존 설정은 비교·병합에만 일시 사용한다. 원본·원본을 포함한 병합 결과·Diff를 DB·로그·캐시·임시 파일에 보관하지 않는다. 브라우저도 localStorage 등 영속 저장을 사용하지 않는다.
- Config/Hook/명령은 검토된 고정 템플릿과 허용 인자로 생성한다. LLM이 실행 코드를 새로 만들지 않는다. 초기 Custom Skill은 자연어 규칙만 다룬다.

## 4. Preview 응답과 비교 범위

`201 { "preview": Preview }`를 반환한다.

| Preview 필드 | 타입·의미 |
| --- | --- |
| id, createdAt, expiresAt | 서버 ID·UTC 시각. 생성 후 10분 만료 제안 |
| status | READY. 검증 실패를 READY로 저장하지 않음 |
| basis | 요청과 대조한 버전 집합 |
| recommendationId, selectedToolIds | 검증된 선택 |
| selectionDigest, contentDigest, fingerprint | 선택·파일 내용·전체 승인 대상의 SHA-256 식별값 |
| evidence | { environment: USER_DECLARED, existingFiles: UNKNOWN/USER_DECLARED/PROVIDED_CONTENT, effectivePermissions: UNVERIFIED } |
| files | 아래 PreviewFile[] |
| policies | 검증한 permissionPolicies와 동일 구조의 배열 |
| warnings | { code, message, targetKey: string 또는 null }[] |

`PreviewFile`의 필드:

| 필드 | 타입·조건 |
| --- | --- |
| targetKey, relativePath | 서버가 검토된 템플릿으로 확정한 대상 |
| action | PROPOSAL / UPDATE |
| beforeHash | 제공된 비교 원본의 SHA-256 또는 null |
| afterHash | 제공할 content의 정확한 UTF-8 bytes SHA-256 |
| content | 사용자에게 보여줄 최종 파일 내용 |
| diff | 제공된 원본과 비교한 통일 Diff 문자열 또는 null |
| comparisonScope | PROVIDED_FILE / EXISTING_UNKNOWN |

이 다운로드 초안은 파일 삭제를 지원하지 않는다. 후속 실제 적용 Feature에서 생성·삭제 동작을 추가하면 별도로 계약한다.
제공된 파일과 비교한 변경은 UPDATE이며 PROVIDED_FILE 범위에서만 유효하다. 다운로드 시점의 PC 파일이 같다는 보장은 아니다.
미제공 파일은 existingState가 USER_SAYS_EMPTY여도 PROPOSAL, beforeHash/diff=null, EXISTING_UNKNOWN이다.
화면에는 **“신규 환경용 설정안 · 기존 파일 미확인”**을 표시한다. 실제 CREATE/UPDATE 또는 유효 권한을 단정하지 않는다.
제공받은 내용의 비교를 실제 PC 검사로 승격하지 않는다. 상위 정책·인증 상태를 모르므로 effectivePermissions는 UNVERIFIED다.

권한과 필수 의존성 검사에 통과한 선택만 READY가 된다. 선택 변경이 필요하면 422와 안전한 fields 안내를 반환한다.
Preview에는 ZIP에 들어갈 설정 및 적용·인증·확인 안내 파일을 모두 포함한다. 승인 후 숨은 추가 파일을 붙이지 않는다.
Secret은 값 대신 환경 변수 참조나 인증 절차로 안내하며 실제 Credential을 Preview에 반영하지 않는다.

## 5. 보관하지 않는 내용과 승인 일치

서버는 Preview ID·선택·정책·대상·버전·해시·상태·시점만 저장한다.
파일 content·Diff·원본은 응답 완료 후 보관하지 않는다. 따라서 Preview 본문을 되돌려 주는 GET endpoint는 없다.
브라우저는 현재 화면의 메모리에서 PreviewInput과 응답을 유지하며 취소·로그아웃·완료 시 해제한다.
새로고침·재접속 후에는 필요한 기존 설정을 다시 제공하고 Preview를 다시 만든다.

다음이 바뀌면 기존 Preview와 승인으로 내보낼 수 없다.

- Project/Developer/Environment 버전, Catalog revision, 도구·컴포넌트·지원 조합·권한 매핑
- 선택 도구·정책·대상 경로·기존 파일 내용·생성 파일 내용
- 생성 템플릿·Adapter 버전, 승인 만료, 프로젝트 삭제

서버는 생성기 버전도 fingerprint에 포함한다. Catalog 갱신 중 생성 결과가 바뀌면 성공으로 저장하지 않는다.
fingerprint는 서버가 계산한다. 클라이언트가 전달한 해시를 검증 없이 신뢰하지 않는다.
해시 입력은 서버가 정의한 고정 키 순서의 JSON으로 직렬화한 basis·선택·정책·생성기 버전·정렬된 파일 목록이다.
파일 목록은 relativePath 오름차순이며 targetKey/action/beforeHash/afterHash를 포함한다.
선택은 ID, 정책은 catalogItemId/key/resourceScope/mappingId 순으로 정렬한다.
contentDigest는 정렬된 파일 목록만, selectionDigest는 선택·정책·basis만 대상으로 한다. 해시는 소문자 64자리 hex다.
UTF-8 원문 파일의 줄바꿈을 해시 계산 뒤 바꾸지 않는다. 후속 Plan에서 직렬화 예제와 공통 fixture를 고정한다.
ZIP 컨테이너의 압축 메타데이터까지 같음을 뜻하지 않으며 **압축 해제 후 경로와 파일 bytes가 Preview와 같아야 한다.**

## 6. 최종 승인

POST /api/projects/{projectId}/config-approvals

```json
{
  "previewId": "preview_example_01",
  "previewFingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "confirmation": true
}
```

위 해시는 형식 예시다. 실제 서버 값과 일치해야 한다.
서버는 소유권·현재 버전·권한·fingerprint·만료를 다시 확인하고 승인 및 Audit를 같은 트랜잭션에서 기록한다.
응답은 `{ "approval": { "id": "...", "previewId": "...", "fingerprint": "...", "approvedAt": "...", "expiresAt": "..." } }`이다.
approval.expiresAt는 Preview 만료를 넘지 않는다. 누락/false confirmation은 422이며 승인을 만들지 않는다.
이 동작은 설정 파일 산출에 대한 승인이다. 외부 계정 연동·실제 명령 실행·향후 다른 변경의 포괄 승인이 아니다.

## 7. 승인한 파일 다운로드

POST /api/projects/{projectId}/config-exports

요청은 `{ approvalId, previewId, previewFingerprint, input: PreviewInput }`이다.
원본을 보관하지 않으므로 Preview 때의 입력을 다시 받아 일시적으로 재생성한다.
최소 보관 metadata 및 현재 상태와 비교하고 파일 해시·fingerprint가 일치할 때만 응답한다.
변경·만료·거부가 확인되면 ZIP을 반환하지 않는다. 다운로드 직전 짧은 트랜잭션에서 상태를 다시 검사한다.
승인 저장만으로 파일 생성·다운로드 완료 상태를 기록하지 않는다.

성공 응답:

- Content-Type: application/zip
- Content-Disposition: attachment; filename="agentfit-config.zip"
- Cache-Control: no-store
- X-Request-Id: 요청 식별자
- X-Configuration-Id: 생성 이력 식별자

ZIP 내부 경로도 허용된 상대 경로만 사용한다. Preview에 있는 파일만 정확한 bytes로 포함한다.
파일 쓰기·로그인·도구 연결을 서버가 사용자의 PC에서 수행했다고 표시하지 않는다.
전송 중 네트워크가 끊길 수 있으므로 서버 이력은 GENERATED만 보장한다. 다운로드 수신 완료를 추정하지 않는다.
같은 유효 승인과 동일 입력의 재요청은 가능하지만 자동 POST 재시도는 하지 않는다. 각 완료된 생성의 이력은 독립 ID를 가진다.
오류는 application/json의 공통 envelope이므로 Frontend는 응답 Content-Type과 상태를 확인한 뒤 파일로 저장한다.

## 8. 생성 이력과 사용자 진술

GET configuration-history의 query는 limit(기본 20, 1–100)과 cursor(서버가 반환한 불투명 값, 최대 512자)다.
정렬은 createdAt 내림차순·id 오름차순이며 다음 페이지가 없으면 nextCursor=null이다. 잘못된 query는 422다.

`items`의 각 항목은 다음 최소 정보를 포함한다.

| 필드 | 타입·의미 |
| --- | --- |
| id, createdAt | 생성 ID·시각 |
| recommendationId, previewId, approvalId | 같은 프로젝트의 추적 ID |
| basis, fingerprint | 생성에 사용한 버전·승인 대상 |
| validity | CURRENT / STALE, 현재 환경·Catalog와 서버가 비교 |
| files | { relativePath, action, afterHash }[]; content·Diff 없음 |
| status | GENERATED |
| verification | { status: NOT_RUN, source: NONE } |
| latestUserReport | 아래 report 또는 null |

서버/로컬 검사 연결이 없는 이 초안에서는 verification을 VERIFIED로 바꾸는 공개 API가 없다.
설치·인증·연결·무해한 사용 확인 안내를 따로 표시하고 모르면 미수행 상태로 둔다.

POST configuration-history/{configurationId}/reports 요청:

```json
{
  "reportedState": "APPLIED",
  "reasonCode": null
}
```

reportedState는 APPLIED/FAILED, reasonCode는 null 또는 COPY_FAILED/AUTH_REQUIRED/DEPENDENCY_MISSING/UNKNOWN이다.
FAILED이면 reasonCode가 필수이고 APPLIED이면 null이어야 한다. 자유 형식 로그·Secret·설정 본문을 받지 않는다.
응답은 `{ "report": { "id": "...", "configurationId": "...", "reportedState": "APPLIED", "reasonCode": null, "source": "USER", "reportedAt": "..." } }`이다.
source와 시각은 서버가 지정한다. 사용자 진술을 verification으로 복사하지 않는다.
모든 이력·승인·Preview metadata·진술·Audit는 프로젝트 삭제에 함께 제거한다. 외부 PC에 내려받은 파일은 서버 삭제 범위가 아니다.

## 9. 오류·프런트 후속 행동

공통 400/401/403/404/413/415/422/429/500/503 규칙을 따른다. 후속 JSON API의 415 code는 UNSUPPORTED_MEDIA_TYPE이다.

| HTTP / code | 상황 | 사용자에게 제공할 행동 |
| --- | --- | --- |
| 404 / PROJECT_NOT_FOUND | 프로젝트 또는 그 하위 Preview·승인·생성 ID가 없거나 접근 불가 | 목록·최신 상태로 이동, 다른 소유 여부 노출 금지 |
| 409 / CONFIG_STALE | basis·Catalog·템플릿·선택·내용이 달라짐 | 추천/입력 확인 → 새 Preview → 새 승인 |
| 409 / RECOMMENDATION_NOT_READY | 오래된 추천 또는 RECOMMENDED가 아닌 결과 | 추천 상태 확인·필요 정보 보완 |
| 410 / PREVIEW_EXPIRED 또는 APPROVAL_EXPIRED | 10분 유효 기간 경과 | 새 Preview·승인 |
| 422 / INVALID_INPUT | DTO·해시 형식·confirmation·기대 항목 불일치 | 해당 입력 수정 |
| 422 / BLOCKED_SELECTION | 거부한 필수 권한·누락 의존성·충돌·미검증 매핑 | 도구 선택·지원 정책 수정 |
| 422 / SENSITIVE_INPUT | 기존 설정 등에 실제 Secret 포함 | Secret 제거 후 다시 입력 |
| 503 / CATALOG_UNAVAILABLE 또는 STORAGE_UNAVAILABLE | 검증 기준 또는 저장소 사용 불가 | 실패 안내, 생성 성공으로 표시하지 않음 |

유효한 approvalId가 없는 내보내기는 거부한다. 임의 ID는 404, 필드 누락은 422로 처리한다.
승인 취소는 이후 내보내기를 하지 않고 화면의 일시 입력을 해제하는 동작이다. 이 초안은 별도 취소 API·백그라운드 적용 작업을 두지 않는다.
추후 승인 취소 endpoint나 로컬 적용 기능을 도입하면 이미 실행 중인 작업의 중단 범위까지 별도 계약한다.
시간 예산·요청 빈도·실제 지원 Client/파일 경로·정확한 권한 매핑은 후속 Plan에서 확인한다.

## 10. 인계와 수용 기준

- B: 선택·호환성·권한 변환·고정 템플릿·해시 재현·만료 규칙, 지원되지 않은 통제의 배제.
- A: 프로젝트 소유권·원자적 승인/생성 기록·삭제 cascade·안전 오류·원본 비보관.
- Frontend: 선택 전 비활성, 정책/Preview/최종 승인 분리, 메모리 입력 재제출, 오류 JSON 처리, 진술과 검증 구분.
- Designer: 기존 파일 미확인·실제 비교 범위·만료·충돌·인증 준비·적용 실패·검증 미수행 문구.
- AI: 추천 이유·자연어 규칙 후보를 제공하며 권한·실행·검증 완료를 결정하지 않음.

후속 인수 사례는 거부 권한, 오래된 basis, 승인 뒤 한 글자 변경, 원본 재제출 변경, 만료, 타인 ID, Secret 입력, Plugin 중복, 다운로드 중단, 사용자 APPLIED 진술을 포함한다.
문서 검토 결과와 실제 권한·Config 동작 시험 결과는 별도로 기록한다.

[API 목차](README.md) · [공통 규칙](common.md) · [추천 API 초안](02-recommendations.draft.md) · [검증 계획](../validation-plan.md)
