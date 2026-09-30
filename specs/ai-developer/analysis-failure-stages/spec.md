# 분석 실패 단계의 안전한 보존

## 목적과 근거

실사용 목표의 실패 원인 파악을 개선한다. 기존 독립 평가1건은247.598초 후ANALYSIS_FAILURE로 종료됐지만 어느 단계인지 알 수 없다. 코드에서 CandidatePipelineError.stage/detail이 있어도 candidate_service_worker가 provider_code만 safe_code로 투영해 단계 정보가 사라짐을 확인했다. **이 관측만으로 과거 실패의 실제 원인을 단정하지 않는다.**

사용자는 목표 안의 설계·계획·직접 구현을 자율 진행하도록 승인했다. 기능별SDD·feature브랜치/push를 유지한다. NVIDIA무료 확인 자료는 제공 가능 답변만 받았으며 실제 자료 미수신이다. 모델 호출0회/유료0원, 개인문서전송/배포0회다.

## 선택한 변경

①원문·stacktrace 기록은 민감정보 위험과 보관 의존이 있어 제외, ②새 실패 메타데이터DTO는 공개/내부 소비자 계약 변경이 커서 제외, ③기존 error 문자열에 고정 단계코드를 추가하는 작은 변경을 선택한다.

`diagnostics.PIPELINE_FAILURE_CODES`에 다음9개 리터럴만 허용하고 기존SAFE_CODES에 합친다:

EXTRACTION_FAILED, GROUNDING_FAILED, OPERATION_EXTRACTION_FAILED, MERGE_FAILED, CLASSIFICATION_FAILED, COVERAGE_REVIEW_FAILED, FEATURE_CURATION_FAILED, PROJECTION_FAILED, DIAGNOSTIC_FAILED.

CandidatePipelineError 처리 우선순위:

1. detail이 정확히CALL_BUDGET_EXCEEDED면 기존CALL_LIMIT.
2. provider_code가 기존/추가SAFE_CODES로 검증되면 해당 안전 코드 유지.
3. 제공자 코드가 없거나 안전하지 않고 stage가정확한str이며 위9개에 포함되면 stage.
4. 이외에는ANALYSIS_FAILURE. 임의 stage/detail/provider_code/예외 문자열을 출력하지 않는다.

v2 실패 외곽은 contract/outcome/error 그대로다. 실패가 성공이나확인필요로 승격되지 않는다. 공개 Profile·질문·HTTP 상태·Spring mock·모델/프롬프트·호출예산/재시도/기한은 변경하지 않는다. 평가의 실패 분모와human_reviewed=false/release_gate_passed=false는 유지한다. 단계코드는 원인 확정이나 모델 품질 개선을 의미하지 않는다.

## 기준선 보존

E:/AgentFit/tmp/worktrees/analysis-runtime의ef6fad5 checkout, 고정10문서/207임시gold, 기존실행기/산출물을 그대로 유지한다. 새 코드 변형은feature/analysis-failure-stages와 별도E:/AgentFit/tmp/worktrees/analysis-failure-stages에서만 작성한다. 중단된baseline run을 새 코드로 이어 쓰지 않는다. 새 실제 평가는 별도변형/manifest로 등록해야 하며 무료확인 전 실행하지 않는다.

## 검증·상한

- 9개stage가 worker→부모process→실제FastAPI경계와 평가score에 안전하게 보존되는지 합성 주입으로 검증한다.
- known provider 우선/호출한도 우선/unknown·비문자열단계 fallback/민감sentinel 부재/성공응답불변을 검사한다.
- evaluator의 실패 상태·gold 분모·releasefalse가 바뀌지 않음을 검사한다.
- 원래worktree의고정해시를재확인하고새branch의기존unit/runtime/contract전체gate와최종독립review1회,정확한CI를확인한다.
- 작업45분후점검, 각테스트180초, 합성process테스트10초, 모델0회/0원, 자동재시도0. 동일원인수정3회실패시가정재검토. 실제평가/실제Spring은계속미검증이다.
