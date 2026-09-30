# 제한된 실제 누락 진단 실행 계획

## 실행 전 조건

1. Task1~3 구현 검증, 전체 unit/runtime/contract/core 통과, 독립 최종 리뷰1회와 필요한 수정 검증.
2. `feature/candidate-provenance-probe` commit/push와 해당 소스 CI 성공.
3. 원래 30회 평가는 terminal이며 기존 결과를 보존한다. 원래 corpus/gold/freeze·이전 증거 파일 해시를 확인하고, 새 도구4파일 해시를 별도 기록한다.
4. 기존 무료 확인 파일 `E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json`을 원본 그대로 검증한다. 만료 연장·유료 대체·새로운 무료 확인 기록 작성은 하지 않는다.

## 고정 범위

- 순서: PUBLIC-01(반복 기능 미반환), PUBLIC-09(동일 증상), PUBLIC-07(대조), 각1회.
- 기존 README corpus와 임시 agent gold. 새로운 실제 기획서/사람 검토 정답이 아니다.
- 모든 단계 DeepSeek 4.1 Flash, 기존64호출/요청·최대1800초/요청, 총192호출 예약·5400초, 재시도0.
- 무료 확인은 매 요청 전에 검증한다. 제공자 오류·만료·범위불일치·예산초과·도구/자료 변경·불완전 진단이면 다음 요청을 중단한다. 중단된 결과는 새 시도로 덮어쓰거나 자동 재실행하지 않는다.

## 명령

작업 위치: `E:/AgentFit/tmp/worktrees/document-input-runtime/ai_service`. 출력은 존재하지 않는 새 디렉터리이며 상위 디렉터리는 이미 있어야 한다. 최초 실행은 아래 명령에서 `--live`·env·access·output 옵션을 빼고 오프라인 preflight로 실행한다.

```powershell
rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m diagnostic_tools.candidate_trace_probe --live --corpus ../specs/ai-developer/04-analysis-provider/independent-profile-evaluation/corpus.json --gold E:/AgentFit/output/independent-profile-v1/gold-v1.json --freeze ../specs/ai-developer/nvidia-review-model-routing/freeze.json --env-file E:/AgentFit/.env --access-confirmation E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json --output E:/AgentFit/output/independent-profile-v1/candidate-provenance-probe-v1
```

env 값은 기존 loader가 메모리에서 NVIDIA 키 하나만 읽고 자식 stdin으로 전달한다. shell로 키를 읽거나 argv·환경·로그에 넣지 않는다. gold는 부모 채점에서만 사용한다. 외부로 보내는 문서는 기존 승인 범위의 공개 자료3개뿐이다.

## 결과 해석

각 요청의 started/terminal/trace를 검증해 완료·실패·미시작을 구분한다. 후보 ID와 위치를 이용해 grounded→classified→reviewed→projected에서 최초 제외/보류 경계를 찾는다. 긴 값이 있는 필드의 전체 null, rejected 후보로 인한 전체 확인 승격 여부도 별도 집계한다.

reviewed 훅은 기능 정리 이후에 있으므로 훅 미관측을 모델 검토 미실행으로 해석하지 않는다. 반복 위치/포함 관계는 의미 정답을 보장하지 않는다. 이번 호출은 원래 응답 재생이 아니므로 이전 실행과의 점수 차이를 개선율로 주장하지 않는다.
