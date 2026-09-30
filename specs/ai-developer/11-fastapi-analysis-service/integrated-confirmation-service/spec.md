# 통합 후보 분석의 확인형 서비스 연결

## 목적과 권한

실사용 가능한 AgentFit AI를 위해 현재 CLI/실험용인 후보 추출→분류→검토→대표 기능 정리 경로를 실제 FastAPI 요청 수명주기에 연결한다. 원문 근거가 있는 제안과 불확실 상태를 함께 전달하고, 연결 종료·전체 기한에 모델 통신을 중단해야 한다. 사용자는 목표 안에서 설계·계획·구현을 별도 승인 없이 진행하도록 명시했으며 SDD, 직접 순차 구현, feature 브랜치 push를 유지한다.

이 기능은 분석 품질을 사용자 수정으로 대체하지 않는다. 실제 문서 판단 오류, 독립 문서 평가, 사람 수정 부담, Spring 확인·저장/버전 경쟁/실패 원본7일 삭제는 전체 목표에 남는다. 서비스 연결 성공을 실사용 완료로 선언하지 않는다.

## 설계 선택

1. **채택:** 기존 요청별 격리 프로세스 안에서 Solar/NVIDIA HTTP를 직접 수행한다. 기존 Solar 서비스와 같은 소유 관계여서 그 프로세스 종료가 열린 통신도 종료한다.
2. 별도 Provider 자식 프로세스를 유지하고 OS별 프로세스 트리를 종료하는 방식은 새로운 Job/process-group 관리가 필요하다. 이번에는 중첩 프로세스를 만들지 않는다.
3. 영구 작업 큐/새 저장소는 Spring의 조율·저장 책임과 합의가 필요하므로 만들지 않는다. 이번 연결은 설정으로 선택하는 동기 내부 HTTP 경로다.

## confirmation-v2 내부 계약

- 서버 설정 `AGENTFIT_ANALYSIS_MODE=integrated-candidates`에서만 활성화한다. 기본 `default`와 기존 `recoverable-solar`는 유지한다.
- 인증 후 body를 읽거나 슬롯을 잡기 전에 `X-AgentFit-Analysis-Contract: confirmation-v2` 헤더가 정확히 한 개 필요하다. v1/누락/중복/다른 값은428 `CONFIRMATION_CONTRACT_REQUIRED`다. 헤더로 서버 모드를 변경할 수 없다.
- 새 응답은 `contract: confirmation-v2`를 포함하고 `outcome`은 `needs_confirmation|failed`다. 품질 승격 전 자동 `complete`는 반환하지 않는다.
- 확인 응답 키는 `contract,outcome,profile,fieldStates,questions,error`이며 HTTP는 `requestId`만 추가한다. `error`는 `REVIEW_CONFIRMATION_REQUIRED`다. 공개 Profile의10필드·근거·null/[] 의미·대표 기능 최대30개는 유지한다.
- `fieldStates`는 정확한10필드다. `suggested`는 non-null 제안이며 `CONFIRM_SUGGESTION` 질문이 필요하다. `unknown`은 null이고 질문이 없다. **v2의 `unresolved`는 null 또는 근거 검증된 non-null 제안을 가질 수 있다.** 기존 v1의 unresolved=null 규칙은 유지한다.
- 질문 키는 기존과 같은 `field,reason,questionId`이며 ID는 `confirm_<field>`. unknown을 제외한 각 필드에 정확히 한 질문, 중복/누락/임의 문구 금지. unresolved 사유는 `REVIEW_ISSUE|CANDIDATE_MISSING`만 허용한다. 실제 제안 값과 원문 근거는 Profile로 전달하며 선택·수정 UI가 활용한다.
- 후보 결과의 unresolvedFields는 그대로 질문 대상이다. rejectedCandidateCount>0, candidateCount=0 또는 needs_confirmation인데 특정 unresolved가 없으면 어느 필드에 영향이 있는지 알 수 없으므로 모든 필드를 unresolved로 표시한다. 후보가0이면 CANDIDATE_MISSING, 그 외 REVIEW_ISSUE다. 기존 non-null 제안은 지우지 않는다.
- 후보 출력의 필수/선택 키·순서와 중복 없는 field 집합·정수 개수·Profile 정합성을 검증한다. `candidate_profile`이 unresolved/rejected/reviewIssue 또는 후보0과 모순되면 거절한다. 내부 진단 원문이나 임의 metadata를 HTTP에 전달하지 않는다.
- 실패 응답은 `contract,outcome=failed,error`만 허용한다. 파이프라인 오류의 안전한 provider code, CALL_BUDGET_EXCEEDED→CALL_LIMIT, 그 외 ANALYSIS_FAILURE를 사용한다. 문서·응답·추론·키·예외 문자열은 오류에 포함하지 않는다.

## 실행·설정·기한

- `UPSTAGE_API_KEY`와 `NVIDIA_API_KEY`는 서버에서 읽어 자식의 stdin으로만 전달한다. argv/환경/일반 로그에 넣지 않는다. 둘 중 하나가 없으면503 `MISSING_OR_INVALID_KEY`로 모델 호출 전 거절한다.
- 선택형 `requirements-integrated.txt`의 LangExtract1.7.0이 필요하다. 설치가 없으면503 `INTEGRATED_RUNTIME_UNAVAILABLE`. 기본 설치와 사용자 공용 환경을 바꾸지 않는다.
- 기본 통합 파이프라인 설정을 사용한다: Solar 추출/분류, GLM5.3 검토, DeepSeek V4.1 Flash 기능 추출/정리, 기본20검토묶음, 총64호출상한, 기존 NVIDIA503 재시도1. 이번에 모델·프롬프트·정규화·분류·평가 기준은 바꾸지 않는다.
- 독립 실행용 post_nvidia_streaming은 기존 자식/요청 기한 계약을 유지한다. 새 post_nvidia_streaming_inline은 같은 입력·응답 제한과 SSE/오류 검증을 재사용하고, 이미 격리된 분석 프로세스에서만 사용한다. inline의 socket timeout은 전체 경과 시간 보장이 아니므로 **요청 전체 기한은 부모의 강제 종료가 보장**한다.
- 통합 모드의 `AGENTFIT_REQUEST_TIMEOUT_SECONDS`는 기본1800, 허용1..3600초. 기본/복구 모드60·최대120초, 업로드10·최대30초, 슬롯2·최대8은 유지한다. 함수 인자와 환경 문자열 범위가 같아야 한다. 잘못된 값은 시작 시 거절한다.
- 전체 기한은 body 수신·추출·분석·응답 준비를 포함한다. 연결 종료·timeout·취소 시 분석 프로세스가 종료된 뒤 슬롯을 반환한다. 세션 상태/원문을 디스크나 DB에 저장하지 않는다.

## 수용 기준

1. 비null 불확실 제안과 근거가 HTTP까지 보존되고 질문·상태가 일치한다. 잘못된 근거/다른 문서ID/누락·중복 질문/v1·v2 혼용/자동 complete는 거절한다.
2. 설정만으로 통합 모드를 선택하고 실제 분석 Worker가 기존 파이프라인을 호출한다. 기본/복구 모드 회귀와 키의stdin전달을 검증한다.
3. 실제 SDK와 합성 응답을 사용하는 전체 추출→근거→검토→대표 정리→확인 어댑터가 실제 HTTP로 응답한다. transport만 로컬 Provider로 바꾸고 추출기·분류기·검토기 자체를 대체하지 않는다.
4. 실제 Solar/NVIDIA 로컬 서버가 통신 중인 상태에서 요청 취소·기한·TCP 연결 종료를 유발한다. worker 종료, Provider 연결 종료, 새 요청의 슬롯 재사용을 확인한다. 응답 시작 전 종료를 성공으로 세지 않는다.
5. 전체 테스트, 실제 SDK runtime_tests, 독립 전체 리뷰, feature push와 정확한 커밋의 Linux CI를 확인한다. 실패/미실행/한계는 남긴다.

Spring 공개 DTO·저장·UI는 이 저장소에서 검증할 수 없으며 팀 합의 완료를 주장하지 않는다. 기본 활성화와 배포는 하지 않는다.
