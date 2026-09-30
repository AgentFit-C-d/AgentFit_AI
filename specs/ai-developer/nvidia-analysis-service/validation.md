# NVIDIA 단독 서비스 연결 검증

## 구현 범위

- `integrated-nvidia` opt-in HTTP→한 키 stdin→실제 요청 자식→NVIDIA-only engine→confirmation-v2. 기본/혼합/복구 경로와 공개 schema는 유지했다.
- 요청 전체 기한 기본1800초/상한3600초, 모델 최대64회/자동재시도0. 요청 자식이 inline NVIDIA 통신을 소유하며 취소/기한에 부모가 종료한다.
- NVIDIA 단독 shim은 Solar 함수 호출·외부 socket·추가 provider 자식 생성을 금지한다. 테스트는 합성 키와 원문, loopback 응답만 사용한다.

## RED/GREEN 증거

- 기존 HTTP baseline5/5.
- 신규 unit11: RED failures7/errors10(미지원 mode/flag)→GREEN11/11 0.721초. 기존 혼합 worker7/7도 통과.
- 신규 runtime5: fixture 옵션 부재로 RED6하위 오류→GREEN5/5 28.963초. 실제 NVIDIA-only SDK10필드, 429·503 각1호출, 명시적 재요청 복구, 기한 초과/TCP 종료/ASGI 취소 후 child/socket 종료와 다음 요청 성공을 검증했다.
- 신규 core-flow1: fixture mode 부재 RED→GREEN1/1 5.749초. 실제 단독 child→mock DRAFT→사용자 수정/확인→429 시 이전 초안/확인본 보존→명시적 재요청→재조회→중복409→삭제. 프로세스3개가 모두 종료되고 합성 제공자 총11회, 모든 경로 nvidia였다.
- 구현852b34a의 task-done 전체 gate: unit1,140건 중1,135통과/5제외(59.550초), runtime20통과(76.318초), contract36통과(8.887초), core-flow5통과(26.734초). 합계1,196통과/5제외, 네 suite 모두 exit0. 기존 Python `<prefix>` 경고는 있으나 검증 실패는 없다.
- 최종 독립 리뷰1회: Critical/Important/Minor0, 신규 unit11/11 및 합성 구조 오류1호출 중단을 reviewer가 별도로 확인했다. [리뷰와 범위 판단](review.md)을 따른다. 정확한 push HEAD의 원격 CI는 브랜치 Actions와 로컬 ledger에서 대조하며, 로컬 성공을 원격 CI 성공으로 간주하지 않는다.

## 실행/인계

`ai_service`의 기존 통합 환경에서 외부 모델 없이 실행한다.

```text
python -m unittest discover -s tests -p test_nvidia_service.py
python -m unittest discover -s runtime_tests -p test_nvidia_service_runtime.py
python -m unittest discover -s core_flow_tests -p test_nvidia_core_flow.py
```

실서비스는 AGENTFIT_ANALYSIS_MODE=integrated-nvidia, AGENTFIT_INTERNAL_TOKEN, NVIDIA_API_KEY를 프로세스 환경에 주입하며 `.env` 자동 로드는 없다. 실제 호출은 현재 계정 무료 범위를 확인할 때까지 보류한다. 이번 연결은 과금 보장/endpoint 실제 호환/모델 품질을 증명하지 않는다.

2026-10-01 [NVIDIA 공식 FAQ](https://docs.api.nvidia.com/nim/docs/product)에서 Developer Program의 프로토타입용 무료 API 접근과 연구·개발·테스트 범위를 확인했다. 운영의 정의에는 실제 최종 사용자에게 제공하는 비테스트 활동도 포함되므로 유료 고객 여부만으로 구분할 수 없다. 이 공개 안내는 현재 계정의 대상 모델·잔여 한도를 확인한 자료가 아니며, 이번 작업의 실제 모델 호출은0회다.

전체 요청 기한은 연결됐지만 독립 품질 평가 runner·별도 variant manifest는 후속이다. 기존 baseline에 새 결과를 덧붙이지 않는다. 실제 Spring/DB/브라우저·질문별 공개 확인 계약·PDF/Markdown 전체 저장 연결·운영 실패 원본7일 삭제는 미검증으로 유지한다.
