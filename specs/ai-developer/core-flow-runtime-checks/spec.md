# 핵심 흐름의 실제 작업자 연결 검증

## 목적

현재 runtime_tests는 실제 LangExtract·분석 자식 프로세스·로컬 HTTP/SSE를 검증하고, contract_tests는 고정 합성 callback을 통한 초안·확인 저장을 검증한다. 두 결과만으로 실제 분석기가 만든 v2 초안이 공개 계약의 저장까지 연결된다고 단정할 수 없다. 기존 핵심 흐름의 이 검증 공백을 메운다.

사용자는 목표 범위의 계획·설계·직접 구현을 자율 진행하도록 승인했다. 기능별 SDD·feature 브랜치/push를 유지한다. 기존 계약을 확장하지 않는 제한된 통합 검증 작업이다.

## 설계

기존 실제 runtime service fixture와 mock TCP fixture를 연결한다. 공개 클라이언트→mock은 실제 loopback TCP, mock→FastAPI는 현재 LocalAnalysisGateway의 ASGI 메모리 통신, FastAPI→작업자는 실제 자식 프로세스, 작업자→합성 Provider는 실제 loopback HTTP/SSE이다. LangExtract와 분석·검증·Profile 변환은 교체하지 않는다. 저장은 기존 MockStore 메모리다.

기존 fixture의 내부 토큰은 매개변수로 받아 새 연결에서 mock-internal을 사용하며, 기존 기본값 synthetic-internal은 유지한다. 모든 키·토큰·문서는 합성 값이다. 부모와 자식에서 외부 연결을 차단한다. 실제 Spring/DB, 브라우저, 실모델, 외부 API, 진단의 운영 삭제는 검증했다고 주장하지 않는다.

## 검증 조건

1. 실제 10필드 분석 결과와 non-null unresolved를 mock에 저장한다. API 버전·documentId·근거·자료형을 기존 검증기로 검사한다. 분석은 DRAFT만 만들고 자동 CONFIRMED는 만들지 않는다.
2. 사용자 수정 PATCH의 전체 data, null/[] 구분, DOCUMENT/USER/UNKNOWN 출처, 버전 증가를 확인한다. 연결을 다시 열어 같은 확인 결과를 조회한다. 같은 expectedVersion 재전송은409이며 저장 상태가 변하지 않는다. 삭제 후404다.
3. 합성 Provider의 손상된 출력을 실제 SDK에 넣어 공개502/AI_UNAVAILABLE, FAILED Attempt, 이전 draft/confirmed 불변을 확인한다. 명시적 재시도만 새 작업자를 만들고 복구한다. 원문 오류 표식·합성 키가 응답·mock 저장에 없어야 한다.
4. Solar 및 NVIDIA 합성 통신 중 공개 TCP 연결을 끊으면 Attempt INTERRUPTED, 작업자 종료, Provider socket 종료, 슬롯 반환을 확인한다. 같은 프로젝트 분석 중409, 종료 후 명시적 재시도 성공을 검사한다.
5. 실제 Provider에 도달한 뒤 mock의 실제 timeout context를 만료시키면504/ANALYSIS_TIMEOUT, 작업자/Provider 종료, 이전 확인값 보존과 명시적 재시도를 확인한다. 짧은 sleep로 기한 경쟁을 만들지 않는다.

별도 core_flow_tests suite와 CI job을 추가한다. 해당 job은 기존 requirements-integrated.txt와 contract_mock/requirements.txt를 함께 설치하고 pip check 및 전용 suite를 실행한다. 기본 설치 의존성과 제품 API/모델/프롬프트/호출 예산은 바꾸지 않는다.

## 상한과 완료 기준

작업45분마다 점검, 각 suite180초, child 요청 최대30초, mock45초, Provider 진입 대기12초, 취소 정리3초, 서버 정리5초. 테스트의 명시적 복구 요청은 사례당1회, 실패 테스트 자동 재시도0. 외부 모델0회·유료0원·원문 전송0회·배포0회.

기준선 checkout/문서/gold/기존 평가 산출물은 읽기 전용으로 보존한다. 새로운 연결이 실패하면 실제 원인을 먼저 규명하고 필요한 최소 수정만 별도 RED/GREEN으로 검증한다. 통합 테스트가 처음부터 통과하면 이미 구현된 동작의 새 증거이며 제품 개선으로 과장하지 않는다. 모든 필수 사례·기존 회귀·최종 독립 검토1회·feature push·정확한 CI 성공으로 이 검증 작업만 완료한다. 전체 실사용 목표의 미검증 항목은 유지한다.
