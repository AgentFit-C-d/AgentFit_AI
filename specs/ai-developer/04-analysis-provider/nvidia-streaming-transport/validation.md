# NVIDIA 전송 비교

## 첫 진단

창작 문서,동일DeepSeek동작추출스키마,512토큰,thinking=false. 각모드1회,총2회. 원문/생성값/키저장없음.

| 모드 | HTTP | 전체 시간 | 첫 content | 종료·원문·두 동작 |
|---|---:|---:|---:|---|
| 일반 | 200 | 17,468ms | 17,468ms | 모두 유효 |
| stream | 200 | 20,841ms | 16,830ms | 모두 유효 |

stream은SSE11event/2789bytes,일반646bytes. 각각224자content,추론글자0. shell31957/PID12084는exit0종료. 드라이버`E:/AgentFit/tmp/nvidia-transport-probe-20260930-v1.py`,결과동일stem.json. 별도verify에서종료/코드/드라이버/요청해시/2arm분모모두일치했다.

두결과는짧은요청과현재모델의stream호환성을확인한다. 긴문서5xx의원인·개선·속도향상은미확인이다. 이를근거로완성응답계약을유지하는SSE어댑터를구현하고긴문서를새평가한다.
