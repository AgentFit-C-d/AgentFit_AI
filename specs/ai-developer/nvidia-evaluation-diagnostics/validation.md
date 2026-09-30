# 호출 진단 검증 기록

2026-10-01 KST. 선택형 `nvidia-call-diagnostics-v1`이며 기존 실제 실패 결과를 재실행하지 않았다. 추가 외부 모델 호출0/유료0/재시도0/배포0.

## 실행한 검증

- 메타데이터 계약 RED3(모듈 없음)→GREEN3; 자식/부모 옵션·envelope RED→GREEN8건. Task1 최종8/8, 1.450초.
- 평가 모드 등록/저장 시험 RED4(옵션 없음)→신규4+기존11 =15/15, 13.411초.
- 실제 SDK·자식·loopback4/4, 20.146초: 정상 on/off의 점수·5호출 동일, 네 번째 GLM 검토503, 첫 DeepSeek429, 전송 성공 뒤 의미 파싱 실패, timeout/cancel 후 프로세스/socket 종료.
- 진단 실패 단계/오류와 실제 결과가 다른 조작3건 RED→신규 단위12/12 GREEN, 6.308초. 허용 enum이어도 상호 모순을 거절한다.
- 오프라인 기존10문서/임시gold207개/코드126파일 고정. 원래 gold·두 실제 결과 폴더·이전 freeze의 SHA256 전후 동일.

## 식별

- variant: `nvidia-call-diagnostics-v1`
- freeze SHA256: `496904267cc23fee2f4e3e3dc18c4cdefb3276e09c55d979593620bf501b4ab4`
- evaluator SHA256: `0dce2ebec826a2bbd825d4d6db30978476931dc1dfd76802c69c4b64857bb990`
- gold SHA256: `5fcdc3a15fdbd346e0e351313639c1ebe2cac02cc36f33abf749d2ff22caa283`

로컬 사전검증 예시(작업 디렉터리 ai_service, 실제 호출 없음):

```text
python -m agentfit_ai.nvidia_evaluation_runner --call-diagnostics
  --corpus ../specs/ai-developer/04-analysis-provider/independent-profile-evaluation/corpus.json
  --gold E:/AgentFit/output/independent-profile-v1/gold-v1.json
  --freeze ../specs/ai-developer/nvidia-evaluation-diagnostics/freeze.json
```

실제 실행은 별도 새 결과 폴더와 유효한 무료 확인 범위가 필요하다. 기존 중단 폴더 재개는 거절한다. 위 명령에 키나 `--live`는 포함하지 않는다.

## 해석

- `requested_model`은 요청한 모델이다. 실패 시 제공자가 모델을 실제 실행했는지는 알 수 없다.
- `failureStage`는 파이프라인의 고정 단계 코드이며 calls의 stage 이름은 실행 구간을 나타낸다. 성공 호출의 `EXTRACTION_FAILED` 같은 이름도 기존 단계 식별자다.
- `available`은 자식에서 정상 수신·검증한 호출 기록이다. `unavailable`과 빈 calls는 실제0호출을 뜻하지 않는다.
- 실제 HTTP 상태번호/원문/키/예외 본문은 저장하지 않는다. 강제 종료 이전의 부분 trace도 전달하지 않는다.
- 정확도 향상, 사람 gold 검토, 실제 Spring·DB·운영 환경은 미검증이다. 기존 실제 평가1/30 제공자 실패는 원인이 소급 확정되지 않는다.
- 최종 전체 gate/독립 리뷰/정확한 구현 SHA CI는 후속 기록에 남긴다.
