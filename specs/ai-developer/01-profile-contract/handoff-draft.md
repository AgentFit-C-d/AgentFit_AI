# AI → Full Stack A·Frontend 인계 계약 검토 초안

상태: 2026-09-25 작성한 **팀 검토 초안**. 팀 합의 또는 구현 완료를 뜻하지 않는다. 기존 [데이터 모델](../../001-project-document-analysis/data-model.md), [HTTP 계약](../../001-project-document-analysis/contracts/http.md), [공개 API 설명](../../../Docs/api/01-project-analysis.md)의 의미를 재정리한다. 변경할 필드가 있으면 공통 계약 담당인 Full Stack A와 소비자인 Frontend가 함께 확인한다.

**아키텍처 변경 확인:** Next.js → Spring Boot → FastAPI 분리가 확정되었다. 이 문서의 `AI 모듈`은 FastAPI 서비스를 뜻하며, Spring Boot는 최종 검증·저장·공개 상태를 책임진다. 내부 서비스 계약은 [FastAPI 서비스 경계·계약 초안](../fastapi-service-contract.md)에서 조율한다. 아래 입력에서 `추출한 텍스트`는 FastAPI 내부 추출 결과이며, Spring Boot가 추출을 담당한다는 뜻이 아니다.

## AI 모듈에 들어오는 정보

- 인증·프로젝트 소유권·요청 크기·동시 실행 제한은 Full Stack A가 검사한다.
- FastAPI는 제한을 통과한 원문과 입력 유형·문서 식별자·호출 취소·시간 예산을 받아 텍스트를 추출한다. 내부 추출 결과의 PDF 페이지·문자 위치 대응 정보를 분석에 사용한다. 전송 형식과 서비스 간 인증은 계약 초안에서 확정한다.
- Credential, 다른 프로젝트 정보, 문서 속 외부 링크·실행 지시는 분석 입력이나 도구 호출로 전달하지 않는다.

## AI 모듈이 돌려주는 정보

| 결과 | 현재 공통 계약 |
| --- | --- |
| Profile 값 | `project_name`, `project_type`, `domain`, `frontend`, `backend`, `ai`, `database`, `deployment`, `features`, `external_integrations`의 10개 필드 |
| 값 의미 | 단일 값은 `string | null`, 목록은 `string[] | null`. `null`은 미정, `[]`는 명시적 없음 |
| 출처 | 문서에서 검증한 값은 `DOCUMENT`, 미정은 `UNKNOWN`. 사용자 수정값 `USER` 판정은 저장 계층에서 수행 |
| 근거 | 문서 ID와 PDF 페이지 또는 전체 추출 텍스트의 code-point `start/end` 위치. 인용문·원문은 영구 결과에 없음 |
| 미확정 목록 | `null`인 필드에서 서버가 다시 계산. Provider가 돌려준 목록을 그대로 신뢰하지 않음 |
| 실패 | 거절·구조 오류·근거 부족·Provider 오류·시간 초과 등을 안전한 코드로 분류. 원본 응답·문서·Secret을 공개 오류·일반 로그에 포함하지 않음. LLM 원본 응답은 별도 오류 추적용 보관 정책을 따른다 |

AI는 값·근거 문자열 존재·원문의 문맥상 확정을 각각 검증한다. 부정·후보·미래·다른 대상·상충 정보를 확정값으로 넘기지 않는다. 분석 성공은 검증된 **초안 후보**이며 확인 Profile을 직접 수정하지 않는다.

## 팀과 맞출 경계

1. **Full Stack A:** FastAPI 호출·취소·시간 초과, 내부 오류 코드와 저장/Audit 매핑, 최종 검증·DRAFT 갱신 조건.
2. **Frontend:** `null`·빈 배열·근거 위치·출처의 표시, 저장 전 수정·직접 작성·재시도 상태.
3. **AI Developer:** Solar Pro 4 평가 시 모델 출력에서 위 공통 결과로 변환하는 Adapter와 구조·근거·의미 검증.

구체적인 내부 타입과 오류 코드명은 Provider 시험 및 A·Frontend 검토 후 공통 schema와 Tasks에 반영한다. 이 문서가 별도의 공개 API나 DB schema를 만들지 않는다.

## 구현된 순수 검증 범위 (2026-09-25)

[SDD 명세](spec.md)·[계획](plan.md)·[작업](tasks.md)에 따라 `ai_service/agentfit_ai/profile.py`에 10개 필드 구조, `null`/`[]`, 출처·미확정 재계산, 근거 code-point 위치와 값의 문자 일치 검증을 구현했다. [로컬 검증](validation.md)은 10개 단위 테스트 통과다. 이 검증기는 **문자열이 해당 근거에 실제로 있는지**까지만 확인한다. 후보·부정·과거/다른 대상 등 문맥상 확정 여부는 별도 의미 검증이 필요하며, Spring Boot 최종 검증과 저장도 아직 연결되지 않았다.
