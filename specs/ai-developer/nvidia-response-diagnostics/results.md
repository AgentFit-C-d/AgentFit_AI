# 오프라인 검증 결과 — 2026-10-02

## 변경

`post_nvidia_streaming` / inline → `nvidia_stream_worker._fetch` → 기존 SSE 조립/검증
실패 → 제한 진단 봉투 → 같은 `AnalysisError('INVALID_RESPONSE')`의
`response_diagnostic` → `ModelCallGate`의 `NN-finished.json`에 연결했다.

기록 항목:

- `http_status`, `content_type`, `error_location`
- `sse_event.index`: data 이벤트 순번(1부터, 주석/메타데이터 제외)
- `data_bytes`, `excerpt`, `truncated`, `redacted`
- JSON 문법 오류일 때 `json_error.char/line/column`(data 해석 텍스트 기준)

발췌는 최대 2,048 UTF-8 바이트, Content-Type은 최대 128바이트,
진단 JSON 전체는 최대 8,192바이트다. 요청/인증 헤더/키/전체 스트림은 기록하지 않는다.
키 또는 인증 표시가 감지되면 발췌 전체를 숨긴다. 검사 후에 자르므로 상한 뒤에
있는 키도 검사 대상이다. JSON escape와 UTF-16/32의 NUL 포함 표현도 숨긴다.
부모는 진단 필드를 허용 목록으로 다시 검사한다.

HTTP 거절은 body를 추가로 읽지 않으며 이벤트를 null로 남긴다.
진단 생성 실패 시 기존 오류 코드만 전달한다. 기존 재시도·시간 제한은 유지한다.

## 검증 근거

| 항목 | 결과 |
|---|---|
| 최초 실패 재현 | 7개 테스트에서 진단 부재 26개 하위 실패 확인 |
| 신규 진단 테스트 | 최종 12개 통과 |
| 전체 단위 테스트 | 1,388개 실행: 1,381개 통과 / 7개 건너뜀 / 실패 0, 76.308초 |
| 저장 성공 응답 재생 | 4/4의 최종 응답 바이트가 기존 39fd07c 및 저장 바이트와 동일 |
| 기존 판정·채점 | 32개 판정(문서 후보 16개 × 모델 2개)과 FR 모델별 채점 동일 |
| 합성 오류 대조 | 11/11 기존 오류 코드 동일 |
| 과거 결과 보존 | 저장 파일 39개 내용 해시 동일 |
| 실제 모델 호출 | 0회 |

재생은 **저장된 조립 응답으로 만든 합성 SSE**를 사용했다. 원래 전송된 SSE 이벤트
또는 네트워크 경계를 재현한 것은 아니다. 한국어 UTF-8을 바이트별로 분할해서도
출력 바이트가 같았다. 정상 응답 및 분류 지침·스키마·정답·서버 판정 파일은 변경하지 않았다.

독립 검토에서 UTF-16/32로 표현된 키를 발췌에서 복원할 수 있는 문제를 발견했다.
수정 전 재현 후 NUL 포함 발췌 전체 숨김을 적용했으며, LE/BE × inline/자식 워커
8개 조합과 부모 재검사를 회귀 테스트에 포함했다. 미해결 중요 검토 지적은 없다.

## 자료

- [최종 재생 결과](E:/AgentFit/output/nvidia-response-diagnostics-v1/replay-final.json)
- [전체 테스트 로그](E:/AgentFit/output/nvidia-response-diagnostics-v1/full-tests.log)
- [로컬 재생 도구](E:/AgentFit/tmp/worktrees/document-input-runtime/work/harness/nvidia-response-diagnostics/replay.py)

로그 중 `calls`는 합성 transport 테스트의 카운터도 포함한다. 이 작업에서 외부
모델 API는 호출하지 않았다. `.env` 및 계정 자격 증명도 읽지 않았다.

## 미검증 / 중단 상태

- 이전 실제 평가 5번 실패의 헤더·원본 이벤트는 저장되지 않아 원인 확정은 불가능하다.
  이번 진단을 과거 기록에 만들어 넣지 않았다.
- 실제 NVIDIA의 새 실패에 대한 기록은 아직 검증하지 않았다.
- 이번 계측은 HTTP/SSE 전송 검증 실패 대상이다. 정상 SSE 조립 이후 분류 JSON/스키마
  검증 실패를 실패한 SSE 이벤트로 간주하지 않는다.
- 배포·실제 Spring 연결·큰 goal 재개 없음. 요청 범위 완료 후 중단한다.
- 이전 동결 manifest는 보존했다. 그중 계측 대상 소스 3개는 변경되었으므로 과거
  실행을 현재 코드로 이어서 실행할 수 없다. 다음 승인된 실험은 새 코드 해시와
  동일 입력/판정 기준을 별도로 동결해야 하며 이번에는 실행·무료 승인 갱신을 하지 않았다.
