# NVIDIA 단독 서비스 연결 명세

## 목적/근거

직전95aff76의 NVIDIA 단독 내부 분석은 Solar 키 없이 실행할 수 있지만 HTTP→요청 작업자에 연결되지 않았다. 전체 핵심 흐름의 Solar 비용 의존을 없애고, 이미 구현된 요청 기한·취소·v2 검증을 실제 단독 경로에 적용한다. 모델 품질 개선이 검증된 것은 아니다. 기존 목표가 설계·계획·직접 구현의 자율 진행을 승인했고, feature별 branch/push를 요청했다.

이번 턴의 실제 모델 호출0/유료0/운영 배포0. 계정의 무료 대상·잔여 한도는 미확인이다. 기존 혼합 baseline 코드·모델·평가자료·실행결과는 원래 analysis-runtime 작업트리에 보존한다. 실제 Spring은 사용자가 승인한 mock/계약 검증으로 한정하며 실제 연동은 미검증이다.

## 선택한 구조

1. 명시적 서비스 모드 `integrated-nvidia`를 추가한다. 기본 모드와 기존 integrated-candidates/recoverable-solar는 그대로다. `/internal/v1/analyze`와 `confirmation-v2`, 현재 Bearer/ID/raw문서 계약은 바꾸지 않는다.
2. NVIDIA 모드의 HTTP는 NVIDIA_API_KEY만 읽는다. UPSTAGE_API_KEY 없이 동작하고 Solar 키를 child/env/argv에 보내지 않는다. 키 누락은 기존503 MISSING_OR_INVALID_KEY, 계약 헤더 누락/구버전은428이다.
3. `run_analysis_process(..., nvidia_only=False)`를 추가한다. nvidia_only는 엄격bool이고 기존 두 bool 모드와 상호 배타적이다. 단독 모드에서는 추가 nvidia_key 인자를 허용하지 않고 generic key가 NVIDIA 키다. child stdin은 정확히 document/documentId/key/mode(integrated-nvidia) 네 문자열이다. 잘못된 모드/키 조합은 생성 전에 거부한다.
4. `execute_nvidia_analysis(document, document_id, nvidia_key)`는 앞선 `analyze_nvidia_candidates`를 inline NVIDIA transport로 실행한다. 공동 최대64회·재시도0·첫 실패 후 중단을 그대로 사용한다. 기존 근거/검토/투영/v2 재검증과 안전한 실패 단계·CALL_LIMIT 우선순위를 유지한다. 별도 provider 자식 없이 요청 자식 하나가 네트워크를 소유한다.
5. 요청 기한 기본1800초/설정1~3600초, 업로드와 문서 추출 시간을 포함하는 기존 absolute deadline을 사용한다. 타임아웃/연결 종료/ASGI 취소는 child와 진행 중 통신을 닫고 admission을 해제한다. 단독 분석 실패 시 이전 mock 확인값을 덮지 않으며 명시적 재시도만 새 요청이다.
6. 정상 출력도 사용자 확인이 필요한 v2 초안으로 저장한다. mock 공개 PATCH/재조회/낙관적 버전/삭제 정책은 변경하지 않는다. 새로운 필드·질문 확인 API·DB 스키마를 추가하지 않는다.

## 대안 및 범위

- 선택한 별도 모드는 baseline 재현과 배포 설정을 구분한다. 기존 integrated-candidates의 의미를 NVIDIA로 덮는 대안은 채택하지 않는다.
- 새 HTTP endpoint는 계약을 불필요하게 늘리므로 만들지 않는다. 결과 body의 provider field도 추가하지 않는다.
- 독립 품질 평가 runner/manifest의 NVIDIA variant는 별도 후속 작업이며 기존 baseline 결과에 덧붙이지 않는다.

## 검증 기준

- unit: 키 한 개의 stdin 계약/비밀 env·argv 배제, 상호 배타·잘못된 옵션 사전 거부, v2 오류 검증, worker 단계 오류와 SDK 부재, HTTP 키 선택/모드 헤더/기한/실패/기본 동작.
- 실제 SDK+loopback HTTP/SSE: 단독 성공10필드/확인 필요, 429·503 각1호출 후 중단/명시적 재시도, 실제 기한 초과/TCP 종료/ASGI 취소 시 child·socket 종료와 admission 복구. 단독 fixture는 Solar transport 사용을 금지한다.
- core-flow: 실제 단독 child→v2→mock DRAFT→사용자 수정/확인→재조회→중복409→삭제. 실제 Spring/브라우저/운영 저장은 미검증.
- 전체 unit/runtime/contract/core-flow, 독립 최종 리뷰1회, feature push 및 정확한 HEAD의 CI.

## 예산

작업45분마다 진척 점검. 각 suite180초. 합성 runtime 요청30초/timeout사례10초, mock45초, 정리3~5초. 모델0회/0원, 실패 자동재시도0, 복구 검증의 명시적 재요청1회. 실제 사용은 계정 무료 범위 확인 이후에만 진행하며 상한 초과 시 유료 전환·모델 대체를 하지 않는다.

## 자기 검토

현재 엔진을 실제 요청 경계에 연결하는 구조 변경이며 기존 사용자 승인으로 진행한다. 무료 과금 보장과 모델 품질은 주장하지 않는다. 기한 책임을 상위 요청 프로세스에 연결해 직전 내부 함수의 미완성 경계를 해소한다.
