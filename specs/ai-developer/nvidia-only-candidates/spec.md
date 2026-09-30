# NVIDIA 단독 후보 분석 명세

## 목적과 확인 근거

현재 통합 분석의 LangExtract 추출·ID 분류는 Solar 고정이며 두 API 키가 필수다. 사용자는 추가 요금 없는 NVIDIA endpoint만 허용했고 유료 Solar 호출은 현재 승인하지 않았다. 이 비용 제약을 해결하는 선택형 내부 경로를 준비한다. 모델 정확도 개선을 입증하는 작업은 아니다.

목표 내 설계·계획·직접 구현은 자율 진행 승인을 받았다. 사용자는 학습/연구 무료라는 안내를 전달했지만 현재 계정의 무료 대상·잔여 한도는 확인되지 않았다. 공식 FAQ도 무료 prototyping과 실제 이용자를 대상으로 하는 production을 구분한다. 계정 UI 연결은 도구 초기화 오류로 확인하지 못했다. 실제 외부 호출 예산은 0이다.

## 범위와 대안

- 선택: 기존 근거·분류·검토·투영 알고리즘을 재사용하고 추출/분류의 sender만 명시적으로 NVIDIA로 선택한다. 한 키, 동일 64회 공동 상한, 자동 재시도 0.
- 기존 Solar 키 필수 경로를 강제로 덮는 안은 기준선 재현을 잃으므로 채택하지 않는다.
- 별도 파이프라인 전체 복제는 근거/검토 계약이 갈라지므로 채택하지 않는다.
- 이번 산출물은 내부 함수와 로컬 SDK 검증이다. FastAPI/작업자 모드·평가 runner·공개 Profile/v2는 변경하지 않는다. 서비스 연결과 별도 평가 manifest는 후속 단계다.

## 계약

1. `analyze_nvidia_candidates(document, document_id, nvidia_key, *, candidate_model=MODEL, review_model='z-ai/glm-5.3', feature_model=MODEL, nvidia_transport=None, observer=None, call_trace=None, review_calls=None, max_calls=64)`를 추가한다. MODEL은 기존 `deepseek-ai/deepseek-v4.1-flash`. 모델은 기존 세 NVIDIA 모델 allowlist만 허용한다. transport 미지정 시 기존 고정 NVIDIA streaming endpoint를 쓴다. Solar/OpenAI fallback이나 env 키 로딩은 없다.
2. 공통 `analyze_integrated_candidates`의 `candidate_model=None` 기본은 기존 Solar 동작이다. NVIDIA 선택 시 `solar_key is None`, `solar_transport is None`, `nvidia_retry_limit == 0`을 강제한다. 입력·옵션·키 검증을 추출/네트워크 전에 끝낸다.
3. LangExtract 추출과 후보 분류에 `nvidia_model=None` 선택 인자를 추가한다. `None`은 기존 Solar, 지정 시 기존 `NvidiaAnalyzer`와 NVIDIA streaming transport. 프롬프트·schema·8192 토큰·후보30개씩 분류·필드 의미 explicit-v1·원문 근거와 검토/투영은 유지한다. 실제 반환 model은 선택 모델과 정확히 일치해야 한다.
4. 모든 기본 LangExtract 호출부터 검토/기능 정리까지 하나의 meter에 포함한다. NVIDIA 전용 경로는 첫 transport 실패를 기억하고 이후 전송을 차단한다. SDK가 예외를 잡더라도 해당 단계는 실패하며 부분 결과를 성공으로 반환하지 않는다. 429/인증/요청/503/timeout 모두 자동 재시도·provider 대체 0.
5. 성공은 기존 candidate 결과이며 `project_candidate_confirmation`으로 기존 v2 검증을 통과해야 한다. 실패는 기존 `CandidatePipelineError`의 단계/안전 코드/호출 예산 사유만 사용한다. 진단에는 원문·인용·키·응답 본문을 넣지 않는다.

## 검증 및 한계

- 신규 로컬 테스트: 한 NVIDIA 키로 전체 원문→실제 SDK→근거→분류→검토→v2, 세 모델의 실제 payload/model 검사, 두 단계 모델 불일치, 호출 상한, 429/503 즉시 중단, 잘못된 옵션의 사전 차단, Solar 호출 금지, 기존 혼합 경로 회귀.
- 주 suite와 기존 runtime/contract/core-flow suite 모두 실행. optional SDK 없는 기본 unit CI는 기존처럼 해당 SDK 테스트만 분리한다.
- 실제 모델 품질/endpoint 기능 호환/계정 과금·한도/실제 Spring은 미검증. HTTP 서비스는 여전히 기존 혼합 설정이다. NVIDIA 단독 평가를 기존 baseline 디렉터리에 기록하지 않는다.
- 예산: 작업 45분마다 진척 점검, 각 suite 최대180초, 합성 provider 호출 timeout600초는 기존 계약값(즉시 로컬 응답), 외부 모델0회·유료0원·자동 재시도0. 기존 기준선 코드/자료/결과·원래 analysis-runtime 작업트리 보존.

## 자기 검토

내부 함수 경계까지의 제한된 구조 변경이다. 세 모델 공개 무료 안내는 계정 증빙으로 취급하지 않는다. 성공률 상승·서비스 적용 완료를 주장하지 않는다. 새 경로의 실패 중단과 기존 경로 호환을 각각 검증한다.
