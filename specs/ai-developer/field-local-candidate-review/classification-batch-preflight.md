# 15후보 진단 사전 검증

2026-10-01, 실제 새 호출 전 확인했다. 기존 분류 실행38073은 exit1로 종료됐으며, Win32_Process에서 남은 `agentfit_ai.nvidia_stream_worker` Python 프로세스가 없는 것을 관측했다. 이 관측은 모든 환경의 종료 처리를 증명하는 별도 테스트는 아니다.

`classification_batch_selftest.py`:6개 통과/0.354초, 외부 API0.

- 두15개 묶음의 후보·문맥을 합하면 실패한 원래30개와 정확히 일치한다.
- 원래30개 요청과 system 지침이 같고, 두 모델의 task 입력·스키마가 같다. 기존 adapter 차이는 유지한다.
- PROVIDER_TIMEOUT/RATE_LIMIT/UNAVAILABLE 코드가 보존되고, 임의 예외 메시지·키는 결과에서 제거된다.
- 무료 확인 거절은0호출,15개가 아닌 입력은 네트워크 전에 거절된다.
- 부모가 잘못된 모델·자유 텍스트 메타데이터를 거절한다. 바깥 시간 초과는 호출 수 미확인으로 남는다.

새 `freeze-classification-batch15.json` SHA256:acf933a21c900067ac71ab490b39163d8d7da09152766f19e0fbe0c1673852a1. preflight exit0,4요청/최대4호출/출력 폴더 없음. `git diff --name-only -- ai_service` 출력 없음: 제품 코드 변경0. 모델의 실제 완료 여부·의미 품질은 아직 검증하지 않았다.
