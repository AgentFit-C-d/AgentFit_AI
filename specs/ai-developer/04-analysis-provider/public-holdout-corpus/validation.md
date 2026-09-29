# 공개 독립 문서 1회 평가

## 자료 고정

기존 AgentFit·MABC·Handoff·합성 튜닝 문서와 무관한 공개 자료를 2026-09-29에 선택했다. 각 URL은 고정 커밋을 가리킨다. 원문은 저장소·평가 결과에 넣지 않고 SHA-256을 확인한 뒤 메모리에서만 사용한다. 정답은 문서의 일부 명확한 값과 고유 인용만 포함한다.

| 사례 | 출처 | SHA-256 |
| --- | --- | --- |
| actual-product | [Actual PRODUCT.md](https://github.com/actualbudget/actual/blob/eb28966d6ca549236dd08b163ffc8570c710e712/PRODUCT.md) | `a254e53f9306722a1db72bc6d3d30be94876aa91447330461a698d0160a3b5d9` |
| mealie-readme | [Mealie README](https://github.com/mealie-recipes/mealie/blob/9f0e221fe9b2ca1ec89d9af1c7b8a785d5b0e048/README.md) | `7a87d6463aba4d2050b89eb4e069b18e5b25ba268372234edbd8d6e8b34650fc` |
| immich-readme | [Immich README](https://github.com/immich-app/immich/blob/a9d102234b8b190cc13b6ac948f4049aa15abb42/README.md) | `27b511ae6ee3be2295c4c1e0674dd0ac5b0c6023d9fdd9187869b1605ff56fad` |

세 원문 모두 고정 해시·고유 인용 검증을 통과했다. 이 평가는 초기 3건으로, 목표했던 사람 검증 독립 기획서 5~10건과 같은 분포가 아니다.

## 실행 및 결과

명령: `python -m agentfit_ai.public_holdout_evaluation --live --env-file E:/AgentFit/.env --output tmp/public-holdout-20260929` (AI 서비스 폴더에서 실행). 출력은 ignored 로컬 `ai_service/tmp/public-holdout-20260929`에만 있다.

| 사례 | 결과 | 안전 오류 | 시간 | 부분 정답 |
| --- | --- | --- | ---: | ---: |
| actual-product | needs_confirmation | PROVIDER_TIMEOUT | 40.063초 | 4개 중 1개 일치, 근거 1개 오류, 값 별칭 미일치 2개 |
| mealie-readme | failed | INVALID_EVIDENCE | 15.159초 | 미채점 |
| immich-readme | failed | INVALID_EVIDENCE | 21.258초 | 미채점 |

모델 호출은 사례별 3회였다. 완전 자동 완료는 0/3, 안전한 확인 초안은 1/3, 분석 실패는 2/3이다. `INVALID_EVIDENCE`의 세부 원인은 원본 응답을 저장하지 않아 이 실행만으로 확정할 수 없다. 평가 결과에는 원문·인용·Profile·키가 없고, 실패 사례를 정답 0으로 채점하지 않았다.

## 검증과 판정

- 고정 원문 3건의 SHA-256·인용 유일성 확인 완료.
- 새 단위 테스트 5건과 AI 전체 테스트 551건 통과.
- 이 세트는 이번 한 번의 관찰 이후 원인 분석·개선에 사용하면 튜닝 자료가 된다. 같은 세트로 개선 후 재평가해도 새 독립 검증으로 부르지 않는다.
- `release_gate_passed=false`. 한국어·PDF·사용자 기획서·사람이 전체 필드/근거를 채점한 새 독립 사례, Spring 저장·확인 E2E가 부족하다.
