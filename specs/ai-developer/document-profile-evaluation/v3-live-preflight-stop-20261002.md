# confirmation-v3 전체 경로 평가 — 실행 전 중단

2026-10-02. 사용자가 승인한 단일 실제 평가는 **모델 호출 전에 중단**했다. 큰 Goal은 paused다.

## 중단 원인

서비스의 `analysis_process.run_analysis_process`와 `analysis_worker.execute_request`는 integrated-nvidia의 명시적 `contract=confirmation-v3`를 지원한다. 그러나 이전 실제 평가에서 사용한 `diagnostic_tools/document_profile_worker.py:148`의 요청 허용 목록은 document/documentId/key/mode/diagnostics뿐이다. contract가 있으면 `INVALID_EVALUATION_REQUEST`로 거절한다.

로컬 대조에서:

- 기본 v2 요청은 관측 도구를 통과해 worker에 전달됐다(합성 반환값 사용).
- 명시적 v3 요청은 worker 진입 전에 거절됐다. 모델 호출은 없었다.
- 서비스 worker를 직접 검사하면 semantic_assessment=True와 contract=confirmation-v3가 다음 경계에 전달된다(합성 경계 검사). 이는 실제 분석의 성공을 뜻하지 않는다.

따라서 서비스의 v3 구현이 없다는 뜻이 아니라 **현재 전체 평가 기록 도구와 v3 선택이 호환되지 않는 문제**다. 사용자의 “설정이 맞지 않으면 모델 호출 전에 멈추기”와 “자동 수정 금지” 조건에 따라 허용 목록을 고치거나 우회 실행하지 않았다.

이전 실행기 `E:/AgentFit/tmp/document_profile_live_once.py` 역시 예전 revision 274ec06만 허용하고 v3를 명시하지 않는다. 그대로 재사용할 수 없다. 이번에는 라이브 실행 진입점을 호출하지 않았으며, 기존 RequestGuard의 로컬 제한 검사만 수행했다.

## 동결 자료

- 코드 HEAD: `e73a43a32ce583fb618b53122479f56b13778311`
- 브랜치: feature/anchor-quote-grounding
- 실제 작업 파일의 바이트 해시 146개: agentfit_ai/diagnostic_tools의 코드·자료, requirements, 평가 JSON. 추적 여부와 관계없이 해당 디렉터리의 실제 파일을 해시했다.
- 실행 코드 디렉터리의 추적된 미커밋 변경 없음. 전체 미커밋·미추적 파일 목록은 freeze.json에 보존. 기존 다른 작업 변경은 건드리지 않았다.
- Python 실행 파일·버전·해시, 로컬 사전 검사 스크립트와 이전 실행기 해시도 기록했다.
- 원문 SHA: `9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451`
- 골드 SHA: `40ecc131c19fb8aa0e0127b67f9a5adf95885ed194a67350d3c89a9e9b328260`
- 원문·골드는 이전 실제 평가의 freeze.json과 동일함을 검사했다. 사전 검사 후 동결한 코드·평가 파일 해시가 모두 동일함을 다시 검사했다.
- 예정 모델/endpoint는 기존 DeepSeek V4.1 Flash, GLM 5.3 및 https://integrate.api.nvidia.com/v1/chat/completions. 호출하지 않았으며 무료 API 권한은 이번 사용자 승인을 근거로 기록했다.

최종 기록 폴더: `E:/AgentFit/output/document-profile-v3-preflight-20261002-final`

freeze.json, source.md, document.txt, gold.json, preflight.py, previous-runner.py, local-tests.txt, local-test-summary.json, execution.json, actual-requests.json, actual-responses.json, result.json을 보존했다. actual-requests/actual-responses는 빈 배열이고 result는 not_executed/Profile=null이다. 실제 모델 최종 응답으로 가장하지 않는다. API 키나 인증 헤더는 읽거나 기록하지 않았다.

## 로컬 검증과 제한 확인

최종 **8/8 통과**, 0.081초. 이 시간은 사전 검사 시간이며 실제 모델 분석 시간이 아니다.

1. 명시 v3가 관측 허용 목록에서 거절됨을 재현.
2. 기본 v2 대조 요청은 worker 진입.
3. 실제 서비스 worker의 v3 선택 전달 검사.
4. 기존 RequestGuard가 51번째 전송을 차단.
5. 단일 요청 600초 제한과 남은 시간보다 2초 짧은 제한 계산.
6. 첫 실패 후 후속 전송 차단.
7. 허용되지 않은 모델 전송 차단.
8. 종료 여유만 남았을 때 요청 시작 차단.

모든 전송은 Mock이고 응용 socket/provider는 차단했다. 실제 새 v3 실행기의 전체 30분 종료·진단 보존까지 검증한 것은 아니다. 이 때문에 실행 게이트는 여전히 실패 상태다.

최초 로컬 검사 8건 중 7건 통과·1건 오류는 대조용 테스트 documentId를 관측 계약의 PUBLIC-XX 형식이 아닌 값으로 쓴 데서 발생했다. 제품 코드는 그대로 두고 로컬 검사 ID만 PUBLIC-01로 맞췄다. 최초 폴더 `E:/AgentFit/output/document-profile-v3-preflight-20261002`도 보존했다. 모델 재시도는 없었다.

## 실제 실행 결과

| 항목 | 이번 결과 |
|---|---|
| 첫 차단 단계 | evaluation_request_validation |
| 오류 | INVALID_EVALUATION_REQUEST |
| 실제 모델 호출 / 재시도 | 0 / 0 |
| 실제 모델 실행 시간 | 0초 — 시작하지 않음 |
| 새 추출·분류·검토·최종 응답 | 모두 미실행 |
| 40개 정상 의미 보존·보류·누락·사람 검토 | 모두 미측정(null), 평가한 의미 0개 |
| 최종 긍정 오답·확인 후보·질문 수 | 미측정 |
| 텍스트 입력 후속 처리·재접속·정보 부족/호환 후보 없음·프로젝트명·Codex | 이번 실제 결과 없음 |

이전 실제 실행(v2)은 25호출/1762.135초, 40의미 보존26·보류9·누락3·사람검토2, 최종 긍정 오답1이었다. 이전 v3 **오프라인 재생**은 보존26·보류11·누락1·사람검토2, 오답1이었다. 이번에는 새 실제 실행이 없어 두 결과와의 개선 비교를 계산할 수 없다. 특히 위치 복구 후 후보 구성의 변화나 모델 응답 변동은 측정하지 않았다.

## 다음에 필요한 최소 변경 — 이번에는 구현하지 않음

1. 평가 관측 도구에서 서비스가 이미 지원하는 계약 값만 허용하고, raw 요청의 contract를 변경 없이 worker에 전달하도록 한다. 알 수 없는 버전은 계속 거절한다.
2. 이번 전용 실행기에서 nvidia_only=True 및 contract=confirmation-v3를 명시한다. 실제 작업 파일 해시를 동결·검사하고, 기존 모델·원문·골드·의미 기준을 유지한다.
3. 50호출/1800초/요청당600초/재시도0/첫 실패 차단, 전체 남은 시간에서 종료·기록 여유를 뺀 요청 제한을 하나의 실행기에서 로컬 검증한다. v3 worker 응답과 기록 도구가 함께 동작하는지도 외부 호출 없이 검증한다.

이번 변경은 사전 검사 스크립트·결과 파일·이 보고서·STATE 기록뿐이다. 분석 코드/관측 도구/모델/프롬프트/스키마/골드 변경, 서비스 적용, 사용자 확정, Spring 저장, 추가 실험, 큰 Goal 재개를 하지 않았다. 중단 사유와 필요한 최소 변경을 보고하고 종료한다.
