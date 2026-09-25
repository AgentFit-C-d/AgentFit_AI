# 2단계 API 초안 — 역할·환경·추천

> DESIGN DRAFT · 2026-09-08 · 구현 승인 전
>
> 공통 PRD의 확정된 제품 요구를 API 형태로 제안한다. 경로·DTO·한도는 후속 Feature의 Spec·Plan·Tasks로 전개해 합의할 설계안이며 구현·호환성 검증 완료가 아니다.

## 1. 범위와 담당

A는 Profile 저장·인증·소유권을, AI는 Capability·추가 질문·설명 근거를, B는 Catalog·호환성·최소 구성·추천 상태를 담당한다.
Frontend는 이 공개 API를 소비한다. Capability를 도출하는 범용 Prompt API·Catalog 수정 API·외부 도구 실행 API를 공개하지 않는다.

모든 경로는 로그인 필수다. 프로젝트 경로는 본인 소유·하위 객체의 소속을 검사한다. JSON 65,536 bytes·추가 필드 거부·안전한 오류 등은 공통 규칙을 따른다.

| Method | Path | 성공 | 담당 |
| --- | --- | --- | --- |
| GET | /api/projects/{projectId}/developer-profile | 200 profile 또는 null | A·AI |
| PUT | /api/projects/{projectId}/developer-profile | 최초 201, 갱신 200 profile | A·AI |
| GET | /api/projects/{projectId}/environment-profile | 200 profile 또는 null | A·B |
| PUT | /api/projects/{projectId}/environment-profile | 최초 201, 갱신 200 profile | A·B |
| GET | /api/tool-catalog | 200 revision·items | B |
| POST | /api/projects/{projectId}/recommendations | 201 recommendation | B·AI |
| GET | /api/projects/{projectId}/recommendations/latest | 200 recommendation 또는 null | B |

최신 추천 조회는 AI를 다시 실행하지 않는다. 전체 추천 이력·관리용 CRUD는 이 초안의 필수 공개 API에 넣지 않는다.

## 2. Developer Profile

PUT은 전체 data를 교체하는 계약이다. expectedVersion은 해당 Developer Profile 버전이며 처음 생성은 0이다.

```json
{
  "expectedVersion": 0,
  "data": {
    "role": "BACKEND",
    "responsibilities": ["API 구현", "데이터 모델 설계"],
    "experienceLevel": "BEGINNER"
  }
}
```

| 필드 | 타입·조건 |
| --- | --- |
| expectedVersion | integer >= 0, 서버 현재 버전과 일치 |
| data.role | FRONTEND / BACKEND / FULL_STACK / AI / DESIGNER 또는 null |
| data.responsibilities | string[] 또는 null. 최대 30개, 항목별 1–200 code points |
| data.experienceLevel | BEGINNER / INTERMEDIATE / EXPERIENCED 또는 null |

200/201과 GET의 응답은 `{ "profile": { "data": ..., "version": 1, "updatedAt": "..." } }`이다.
없으면 GET은 `{ "profile": null }`이며 값이 미정인 Profile과 구분한다.
원문에서 역할·경험을 임의로 확정하지 않는다. 미정 저장을 허용하며 추천에 꼭 필요하면 질문으로 반환한다.

## 3. Environment Profile

브라우저 입력을 실제 PC 검사 결과로 취급하지 않는다. 이 endpoint에서 받은 정보의 출처는 서버가 USER_DECLARED로 설정하며 클라이언트가 VERIFIED·SYSTEM을 지정할 수 없다.

```json
{
  "expectedVersion": 0,
  "data": {
    "os": { "family": "WINDOWS", "version": "11" },
    "client": { "id": "claude-code", "version": null },
    "runtimes": [{ "name": "node", "version": "24.0.0" }],
    "installedComponents": [],
    "configurationKnowledge": "UNKNOWN",
    "authenticationReadiness": []
  }
}
```

위 버전·구성은 DTO 설명용 사용자 진술 예시이며 실제 지원 조합의 검증 결과가 아니다.

| 필드 | 타입·조건 |
| --- | --- |
| data.os | { family: WINDOWS/MACOS/LINUX/OTHER, version: string 또는 null } 또는 null |
| data.client | { id: string, version: string 또는 null } 또는 null |
| data.runtimes | { name: string, version: string 또는 null }[] 또는 null |
| data.installedComponents | { catalogItemId: string 또는 null, name: string, version: string 또는 null }[] 또는 null |
| data.configurationKnowledge | UNKNOWN / USER_SAYS_EMPTY / HAS_EXISTING |
| data.authenticationReadiness | { serviceId: string, state: READY/NOT_READY/UNKNOWN }[] 또는 null |

위 data의 여섯 키는 모두 제출한다. 항목 문자열은 최대 200 code points, 각 배열은 최대 30개이며 null은 미확인, []는 사용자가 명시한 없음이다.
installedComponents에 Catalog ID가 없더라도 이름으로 기존 구성을 기록할 수 있지만 검증 도구로 자동 승격하지 않는다.
authenticationReadiness는 준비 여부만 받고 API key·token·password·인증 코드·실제 Credential은 받지 않는다.

응답은 `{ "profile": { "data": ..., "source": "USER_DECLARED", "version": 1, "updatedAt": "..." } }` 또는 GET의 profile=null이다.
기존 설정 내용은 이 Profile에 저장하지 않는다. 후속 Preview 요청에서 필요한 정제된 파일만 일시적으로 받는다.

## 4. Profile 변경과 충돌

Developer·Environment의 버전은 각각 독립적이다. 두 Profile PUT은 전체 data와 expectedVersion을 필수로 받는다.
없는 Profile 생성 시 expectedVersion!=0, 갱신 시 버전 불일치는 409 VERSION_CONFLICT다.
성공하면 해당 버전이 증가하고 그 값에 의존한 기존 추천·Preview·승인은 STALE로 취급한다. 이전 승인으로 Config를 계속 생성하지 않는다.

서버는 확정 Project Profile 버전·Developer 버전·Environment 버전·Catalog revision을 함께 추천의 basis로 기록한다.
이 값은 Client가 성공 상태를 주장하기 위한 필드가 아니라, 서버의 현재 상태와 비교할 동시성 근거다.

## 5. 읽기 전용 Tool Catalog

GET /api/tool-catalog의 선택 query는 clientId·osFamily·capabilityId다. 모두 단일 값만 허용하며 정의하지 않은 query는 422다.
첫 Catalog 목표가 약 15~20개이므로 이 초안에서는 전체 필터 결과를 반환한다. 도구 수 확장 시 페이지네이션은 별도 계약 변경으로 처리한다.

```json
{
  "revision": "catalog_example_01",
  "items": [
    {
      "id": "tool_example_01",
      "name": "예시 문서 참조 구성",
      "kind": "PLUGIN",
      "version": "example-version",
      "capabilityIds": ["cap_document_reference"],
      "components": [
        { "id": "component_example_01", "kind": "MCP", "name": "예시 구성요소" }
      ],
      "dependencyIds": [],
      "conflictIds": [],
      "sourceUrl": "https://example.org/catalog-example",
      "verification": {
        "status": "NOT_VERIFIED",
        "checkedAt": null,
        "supportMatrix": []
      }
    }
  ]
}
```

합성 예시 항목은 실제 도구가 아니며 NOT_VERIFIED라 추천 대상으로 사용할 수 없다. URL도 DTO 형식 설명용이다.

| Catalog 필드 | 의미 |
| --- | --- |
| kind | MCP / SKILL / HOOK / PLUGIN / RULES, 배포 단위의 종류 |
| components | 포함 구성요소 ID·종류·이름. Plugin과 구성요소를 독립 도구 수로 중복 집계하지 않음 |
| dependencyIds, conflictIds | Catalog 배포 단위/구성요소의 정해진 ID 참조. 모호한 이름 비교로 대체하지 않음 |
| verification.status | VERIFIED / NOT_VERIFIED / EXPIRED / FAILED |
| supportMatrix | { id, osFamily, clientId, clientVersion, runtimeRequirements, componentVersions, permissionMappingId, checks, checkedAt }[] |
| checks | { documentation, format, standalone, combination } 각 값 PASS/FAIL/NOT_RUN |

supportMatrix의 실제 검사 항목·버전이 채워진 범위만 추천한다. checks의 NOT_RUN을 PASS로 처리하지 않는다.
B는 버전·컴포넌트·의존성·권한 변경 시 revision을 변경하고 영향받은 검증을 무효화한다.

## 6. 추천 생성

POST /api/projects/{projectId}/recommendations

```json
{
  "expectedVersions": {
    "project": 1,
    "developer": 1,
    "environment": 1
  }
}
```

project는 Project.version이며 확인 Profile이 있어야 한다. Developer/Environment가 아직 없으면 해당 버전은 0이다.
현재 버전과 다르면 409 VERSION_CONFLICT, 확인 Profile이 없으면 409 PROFILE_NOT_CONFIRMED다.
입력 부족이 정상 판단 결과이면 AI 장애처럼 오류로 만들지 않고 NEEDS_INFORMATION으로 저장한다.

서버는 현재 데이터와 Catalog를 바탕으로 Capability → 후보 → 호환성·포함관계·중복·충돌 → 최소 구성을 판정한다.
LLM이 Catalog 밖 ID·미검증 권한·새 실행 코드를 만들면 후보로 통과시키지 않는다.

| Recommendation 필드 | 타입·의미 |
| --- | --- |
| id, createdAt | 서버 ID·UTC 시각 |
| status | RECOMMENDED / NO_ADDITIONS_NEEDED / NEEDS_INFORMATION / NO_COMPATIBLE_TOOLS |
| validity | CURRENT / STALE. 현재 Profile·Catalog 기준과 서버가 비교 |
| basis | { projectVersion, developerVersion, environmentVersion, catalogRevision } |
| evidenceLevel | PLAN_ONLY / ENVIRONMENT_DECLARED. 실제 설정 파일 검사는 Preview 단계에서 별도 표시 |
| capabilities | { id, name, reason, sourceFields: string[] }[] |
| items | { catalogItemId, catalogVersion, supportMatrixId, required, reason, permissionOptions, authenticationRequirements }[] |
| questions | { field, reason }[]. 정보 부족 결과에만 필요한 질문 |
| reasons | { code, message, sourceFields: string[] }[]. 추가 불필요·미지원 조건 설명 |

permissionOptions는 `{ key, resourceScope, supportedPolicies, defaultPolicy, mappingId }` 배열이다.
supportedPolicies는 ALWAYS_ALLOW/ASK_EACH_TIME/DENY 중 해당 Client·도구·scope에서 검증된 값만 포함한다. 아직 선택된 권한이나 실행 승인이라는 뜻이 아니다.
후속 Preview에서 외부 연결·쓰기·실행 구성 선택을 명시적으로 받고 지원 작업의 기본은 ASK_EACH_TIME으로 둔다.

상태별 불변 조건:

- RECOMMENDED이면 items에 하나 이상의 검증 후보가 있다. 최소 기본 구성과 required=false인 선택 항목을 구분한다.
- NO_ADDITIONS_NEEDED이면 items=[]이고 현재 구성으로 충분하다는 근거가 있다.
- NEEDS_INFORMATION이면 items=[]이며 필요한 질문이 하나 이상 있다.
- NO_COMPATIBLE_TOOLS이면 items=[]이며 부족한 지원 조건이 있다. 존재하지 않는 도구를 만들어 반환하지 않는다.
- 정상 빈 결과와 분석 실패를 구분한다. AI/판정 실패는 안전한 오류이며 성공 Recommendation을 만들지 않는다.

201 응답은 `{ "recommendation": Recommendation }`이다.
GET latest는 같은 형태 또는 recommendation=null을 반환하고 현재 basis와 다르면 validity=STALE로 표시한다.
오래된 결과를 읽을 수는 있지만 새 Preview 입력으로는 사용할 수 없다.

## 7. 실패와 프런트 처리

| HTTP / code | 발생 상황 | 다음 행동 |
| --- | --- | --- |
| 400 / INVALID_INPUT | JSON 문법 | 요청 형식 수정 |
| 401 / UNAUTHENTICATED | 세션 없음·만료 | 로그인 |
| 403 / FORBIDDEN_ORIGIN | 출처 불일치 | 같은 서비스에서 재시도 |
| 404 / PROJECT_NOT_FOUND | 타인·없는 프로젝트 | 목록으로 이동 |
| 409 / VERSION_CONFLICT | 기대 Profile 버전이 오래됨 | 재조회·사용자 확인 |
| 409 / PROFILE_NOT_CONFIRMED | 확인 Profile이 없음 | 첫 Profile 확인·저장 |
| 409 / RECOMMENDATION_BUSY | 같은 프로젝트 추천 생성 중 | 완료 확인, 자동 중복 요청 금지 |
| 413 / INPUT_TOO_LARGE | JSON body 한도 초과 | 입력 수정 |
| 415 / UNSUPPORTED_MEDIA_TYPE | JSON이 아닌 요청 | Content-Type 수정 |
| 422 / INVALID_INPUT 또는 SENSITIVE_INPUT | 잘못된 값·추가 필드·Secret | 안전한 fields 안내에 따라 수정 |
| 429 / RATE_LIMITED | 서버가 정한 작업 한도 | Retry-After 후 사용자 재시도 |
| 502 / AI_UNAVAILABLE 또는 AI_INVALID_OUTPUT | 설명/Capability 생성 실패 | 기존 결과 보존·새 요청 |
| 503 / CATALOG_UNAVAILABLE 또는 STORAGE_UNAVAILABLE | Catalog/저장소 사용 불가 | 기존 결과를 현재 추천 성공으로 표시하지 않음 |
| 504 / RECOMMENDATION_TIMEOUT | 후속 Plan에서 정할 처리 기한 초과 | 실패 안내·기존 결과 확인 |

Rate limit·시간 예산은 후속 Plan에서 부하·실제 모델 조건으로 확정한다. 기존 분석 API의 60초 목표를 추천 API에 검증 없이 복사하지 않는다.

그 밖의 예상하지 못한 서버 오류는 500 INTERNAL_ERROR로 반환한다.

## 8. 후속 명세 완료 조건

정확한 Catalog·지원 조합·Capability 분류·권한 매핑·질문 우선순위·예산을 B·AI·A·Frontend가 맞춘다.
조건 변경 경쟁 상황, 추가 불필요·정보 부족·후보 없음, 실제 지원 범위와 미검증 항목 배제를 인수 사례로 확인한다.
이 설계를 후속 Feature의 Spec·Plan·Tasks에 연결한 뒤 구현한다.

[API 목차](README.md) · [공통 규칙](common.md) · [설정 API 초안](03-configuration.draft.md) · [공통 PRD](../PRD.md)
