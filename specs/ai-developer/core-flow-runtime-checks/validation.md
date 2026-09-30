# 핵심 흐름 runtime 검증 기록

## 구현과 실제 실행 범위

2026-10-01. `feature/core-flow-runtime-checks`, 기준 커밋 `a5657b4bb07598dbf681d777e28c71aac9f23ffb`.

제품 코드·기본 서비스·OpenAPI·모델·프롬프트는 변경하지 않았다. 기존 runtime fixture에 내부 토큰을 지정하는 선택 인자를 추가했으며 기존 기본값은 그대로다. 새 전용 suite는 기존 mock의 TCP 서버와 실제 FastAPI/자식 작업자/SDK를 연결한다. CI에 통합과 mock 의존성을 함께 설치하는 `core-flow-runtime` 검증을 추가했다.

공개 요청과 합성 Provider 통신은 실제 loopback TCP/HTTP/SSE, mock→AI 앱은 현재 ASGI 메모리 통신이다. 저장은 메모리 MockStore다. 모델 호출 결과만 합성 응답이며 LangExtract·분석 단계·근거 검사·v2 변환은 실제 코드를 사용한다. 실제 Spring HTTP/DB 연결로 표현하지 않는다.

## 새 필수 사례

| 사례 | 확인하는 결과 |
| --- | --- |
| 실제 분석→수정→확인→재접속→중복→삭제 | 10필드·non-null unresolved 보존, 자동 확정 없음, null/[]와 출처, version+1, 재조회 동일, 재전송409, 삭제404 |
| 손상된 Provider 출력 | 공개502/AI_UNAVAILABLE, 실패 Attempt, 기존 초안·확인본 유지, 자동 재시도 없음, 명시적 재시도 복구, 키·상세 표식 미출력 |
| 공개 TCP 종료 | Solar/NVIDIA 합성 응답을 받는 중 중단, INTERRUPTED, 실제 자식·Provider socket 종료, 중복409, 슬롯 반환 후 명시적 재시도 |
| mock 시간 초과 | 실제 Provider 도달 후 실제 timeout을 결정적으로 만료,504/ANALYSIS_TIMEOUT, 작업자/소켓 종료, 이전 확인값 보존, 명시적 재시도 |

처음에는 fixture에 `internal_token` 인자가 없어 4테스트/5하위 오류로 실패했다. 해당 선택 인자를 추가한 뒤 4/4 통과(20.300초). 제품의 실패를 재현한 것으로 해석하지 않는다. 실패 입력·취소·기한·버전 충돌은 검증의 음성 대조군이다. 이후 10필드 값 전체를 명시적으로 검사하도록 assertion을 강화했고 최종 gate에 포함한다.

전용 환경 `pip check`: No broken requirements found. 모델 API/실제 키/.env 없이 실행했다. 외부 모델0회·유료0원·개인문서 전송0회·배포0회다. 기존 Python prefix 안내는 동일하며 종료 코드로 성공 여부를 판정한다.

전체 회귀 검증은 다음과 같이 통과했다. 각 suite의 종료 코드는0이다.

| suite | 결과 | 시간 |
| --- | --- | --- |
| tests | 1,123개 실행,1,118 통과·5 skip | 61.476초 |
| runtime_tests | 11/11 | 47.572초 |
| contract_tests | 36/36 | 9.264초 |
| core_flow_tests | 4/4, 전체10필드 assertion 포함 | 20.530초 |

기준 커밋 대비 agentfit_ai 제품 코드의 diff는 없고, 원래 analysis-runtime checkout의 추적 파일 변경도 없음을 확인했다. 최종 task-done gate·독립 검토·push 및 정확한 CI는 후속 실행 근거로 기록한다.

## 한계와 후속 검증

- 이 테스트는 고정된 합성 Provider 결과에 대한 연결 검증이다. 실제 문서 정확도나 정답률 개선을 뜻하지 않는다.
- 공개 질문별 재조회/사용자 확인 계약은 현재 API에 없으며 이 작업이 추가하지 않는다. 수동 Profile 확인 저장만 현재 계약대로 시험한다.
- 실제 Spring/PostgreSQL의 인증·영속성·트랜잭션·삭제/백업, 브라우저 UI, 배포 프록시 및 실제 외부 Provider 비용/취소는 미검증이다.
- TEXT를 이 전체 흐름에서 확인한다. PDF/Markdown 파서 검증은 별도 기존 suite에 있으며 이 연결의 검증으로 합치지 않는다.
- 기존 고정 평가의 문서·모델·정답·결과는 변경하지 않는다. 계정별 무료 상태와 Solar 유료 사용이 미확인/미승인이므로 실제 평가는 재개하지 않았다.
