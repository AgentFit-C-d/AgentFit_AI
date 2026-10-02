# 검토 불일치 후보 보존: 명시 선택 confirmation-v3

사용자가 2026-10-02 A안과 응답 계약 확장을 승인했다. 작은 범위로 직접 구현하고 저장 응답 재생으로만 검증한다. 큰 Goal은 paused다.

## 계약 선택

- 기존 `X-AgentFit-Analysis-Contract` 헤더에 `confirmation-v3`를 정확히 한 번 지정한다. 새 옵션 헤더보다 기존 버전 선택 경계를 재사용하는 방식이 작고 응답의 실제 계약도 명확하다.
- v3는 현재 `integrated-nvidia`의 의미 분류 경로만 지원한다. 다른 모드·알 수 없는 버전·중복 헤더를 거절한다.
- v2 기본 동작·응답 형식·worker 요청은 유지한다. v2 응답에 확장 키를 보내지 않는다. 버전 불일치 응답도 거절한다.
- `default` 모드의 기존 무헤더·단일 v2 헤더 처리는 호환성을 위해 유지한다. 이 모드에서 새 v3·미지원 버전·중복 헤더는 분석 전 거절한다.
- v3 성공 응답은 v2의 의미·Profile·modelDecisions를 유지하고 필수 `reviewDispositions` 배열을 추가한다. 거절 후보가 없으면 빈 배열이다.
- 항목은 정확히 `{candidateId, disposition: "needs_confirmation", reason}`. reason은 기존 검토의 wrong_field/not_current/not_product_fact/insufficient_evidence 코드다.
- 후보 ID로 modelDecisions의 원문 값·candidate 위치·documentId를 참조한다. 원시 모델 판단·근거·decision은 수정하지 않는다. 검토 후 보류는 사용자 직접 확정과 다르다.
- 소비자는 기존 `modelDecisions.decision == needs_confirmation` 후보와 `reviewDispositions` 후보를 ID로 합쳐 확인 대상으로 처리한다. raw supported/confirmed만 보고 사용자 확정이나 긍정 채택으로 해석하면 안 된다. 해당 원문 위치는 긍정 근거에서 제외되며 동일 값의 독립 정상 위치는 유지할 수 있다.
- mock은 `create_mock_app(ai_app=..., analysis_contract='confirmation-v3')` 또는 `LocalAnalysisGateway(..., contract='confirmation-v3')`로 명시 선택한다. mock 분석 응답에만 `review`를 추가 전달하고 기존 v2 mock 응답은 유지한다. 기존 공개 Spring OpenAPI 및 실제 Spring 저장은 수정하지 않는다.

## 검증 불변식

- 알려진 원문 연결 후보만 참조하며 ID 중복·미존재·알 수 없는 사유/키/상태를 거절한다.
- v3 생성 시 실제 검토 거절 ID 집합과 사유 집합이 일치해야 한다. 누락 사유를 임의 생성하지 않는다.
- 후보 원문 연결은 기존 엄격한 문서 검증을 통과해야 한다. 해당 필드는 unresolved 상태여야 한다.
- 보류 후보의 원문 위치를 긍정 Profile의 채택 근거로 사용할 수 없다. 동일 문자열이 독립적인 정상 후보 위치에 있으면 그 후보 근거의 긍정 값은 유지한다.
- v2 모델 입력, 프롬프트, 스키마, 추출, 정답, Spring 저장은 변경하지 않는다. 저장된 동일 응답의 v2 재생 결과가 완전히 같아야 한다.

## 직접 실행 순서

1. 동결 fixture, 현재 실패 테스트 및 v2 동일성 테스트.
2. 검토 사유의 선택형 내부 전달과 별도 응답 항목 생성/검증.
3. worker/프로세스/HTTP 계약 협상 및 mock 소비자의 검증·전달.
4. R1–R6, 별도 합성 오답, 잘못된 연결·중복·부정한 긍정 근거 검사.
5. 네트워크/모델 호출 차단 재생, 40의미와 확인 부담 보고, 독립 리뷰, feature 브랜치 기록 후 종료.

네트워크를 열지 않는 ASGI in-process HTTP와 자식 프로세스 stdin/stdout을 사용한다. 로컬 실험 호출 수0, 재시도0. 실제 Spring 호환성·운영 배포 미검증. Codex/이름/텍스트anchor/처리시간은 미해결로 둔다.

## 실행 완료

결과는 `review-preservation-v3-report-20261002.md`에 기록했다. R1–R6와 합성 오답·괄호 이름 우회 회귀를 통과했다. 초기 전체 회귀에 섞인 기존 loopback TCP 테스트는 최종 오프라인 검증에서 제외했으며 초기 실행 이력도 보존했다.
