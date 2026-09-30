# NVIDIA 평가의 안전한 호출 진단

## 해결할 문제

고정 평가 PUBLIC-01/run0은 약20분50초 뒤 PROVIDER_UNAVAILABLE로 실패했다. 기존 결과는 제공자 HTTP5xx 범주만 남겨 어떤 모델·단계에서 실패했는지 구분할 수 없다. 이 기록을 덮어쓰거나 자동 재실행하지 않는다.

## 동작

- `--call-diagnostics`를 명시한 별도 NVIDIA 평가에서만 진단을 저장한다. 공개 confirmation-v2와 서비스 기본값은 유지한다.
- 동일 분석 함수·모델·64호출 상한·1800초 요청 기한·재시도0·무료확인 정책을 사용한다. 추출/분류/검토/기능 동작이나 정답 기준을 바꾸지 않는다.
- 진단 계약 `analysis-call-metadata-v1`: status `available`/`unavailable`, unavailableReason, failureStage, calls. 각 호출은 stage/provider/requested_model/call_index/elapsed_ms/response_bytes/transport_completed/attempt/retry_of_call_index/provider_error의 기존 메타데이터다.
- 원문·Profile 값·인용·키·URL·임의 예외 문자열·응답 본문은 저장하지 않는다. 모든 필드/타입/열거값/개수/순서를 부모 프로세스에서 다시 검증한다. 최대64행, JSON 내부 envelope 총량은 기존1,500,000bytes 상한을 유지한다.
- 요청 모델은 허용된 DeepSeek4.1Flash·GLM5.3뿐이다. 실패 시 실제 모델 처리 여부는 알 수 없으므로 requested_model로 명확히 표현한다. 정확한 HTTP 상태는 기존 전송 계층에서 버려졌으므로 이번에도 안전한 범주만 제공한다.
- 사용한 호출의 완료·실패 기록은 자식이 정상 응답할 때 전달한다. 기한/강제종료/잘못된 envelope에서는 unavailable로 표시하고 calls는 비운다. 이는 실제0회가 아니라 기록을 얻지 못했다는 뜻이다. 취소 시 자식을 종료하고 기존 started-only를 보존한다.
- 선택형 내부 요청만 diagnostics 문자열 태그를 추가한다. 기본 내부 요청/응답은 기존 그대로다. 진단 요청은 `result`와 `diagnostics`의 엄격한 envelope를 받으며 부모는 result를 기존 검증기에 통과시킨 뒤에만 진단을 채택한다.
- 새 freeze/실험 식별자는 `nvidia-call-diagnostics-v1`; 결과 행에 diagnostics를 추가한다. 기존 점수 형식은 그대로 유지한다. 구형 결과 폴더·started-only·제공자 실패 이후에는 추가 호출하지 않는다. 새 기록 역시 외부 실패 시 전체 평가를 중단한다.

## 완료 근거

1. 단계별503/429, 의미 계약 실패, 정상 완료를 합성 자료로 실행해 모델·단계·순서·오류를 구분한다.
2. 원문/키/임의 오류를 진단에 주입하면 거절하며 기본 모드가 진단 envelope를 수락하지 않는다.
3. 실제 자식·LangExtract·loopback에서 진단 on/off의 점수가 같고 provider 호출도 같음을 확인한다. 시간초과·취소 후 자식/socket 종료를 확인한다.
4. 새 평가의 진단 저장·재읽기·손상 거절·중단/재시작 차단을 로컬 시험한다. 기존 평가 회귀 검사를 유지한다.
5. 신규 freeze는 모든 변경 완료 후 별도 파일로 생성한다. 원문/gold/이전 freeze/실제 결과 폴더는 변경하지 않는다.

## 예산과 한계

이번 작업 추가 외부 호출0/유료0/재시도0/배포0. 합성 요청30초·timeout시험10초, 대상시험120초, suite당180초, CI관찰10분, 구현60분마다 상태 점검.
사람 gold 검토·실제 모델 정확도·실제 Spring/DB·운영 검증은 별도 미완료다. 관측 기능 자체가 분석 정확도를 높였다고 주장하지 않는다.
