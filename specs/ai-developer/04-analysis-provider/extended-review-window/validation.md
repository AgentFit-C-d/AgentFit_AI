# 긴 의미 검토 기한 검증 기록

## 구현

- 공개 PRD 평가 전용 `--source-selector --accuracy-first --extended-review-window`는 전체 600초, 필드 120초, 의미 검토 16,384 출력 토큰을 허용한다. 기본 분석기 60초·평가의 기존 300초 설정은 유지된다.
- 의미 검토 응답의 형식 검증 실패 사유는 허용된 고정 코드일 때만 안전한 평가 진단에 남긴다. 원문·원본 응답·키·Profile을 기록하지 않는다.
- 전체 `python -m unittest discover -s tests -q`: 625건 통과.
- 구현 커밋 `74577f9`을 `feature/extended-review-window`에 push했고 Linux CI `36540615116`가 성공했다. CI 통과는 분석 품질 합격을 뜻하지 않는다.

## 이미 튜닝한 Campfire PRD 실험

동일 설정을 두 번 실행했다. 각 실행은 확률적 모델 응답이 달라 반복 재현성과 원인 추정을 제한한다.

| 실행 | 결과 | 의미 검토 | 부분 정답 | 정답 밖 값 | 총 경과 |
|---|---|---|---:|---:|---:|
| 첫째 | 확인 필요, `SEMANTIC_REVIEW_INVALID` | 응답 완료, 9,325/16,384 토큰, 형식 검증 거부 | 7/7 | 33 | 94,648ms |
| 둘째 | 확인 필요, `INCOMPLETE_RESPONSE` | 16,384/16,384 토큰, 응답 미완료 | 7/7 | 30 | 178,030ms |

첫 실행 당시에는 검토 사유 코드가 안전 결과에 기록되지 않아 정확한 검증 사유를 확인할 수 없다. 사유 추적을 추가한 뒤 둘째 실행은 출력 상한에 걸려 새 사유를 얻지 못했다. 두 실행 모두 자동 완료 0건이며, 정답 밖 값은 사람 검토 전이다. 5문서 확대 조건을 충족하지 못했으므로 기한 연장 방식의 확대·기본값 승격을 중단한다. 후속 작업은 검토 범위 분할과 필드별 검증 누락 방지를 다룬다.

## 산출물

- ignored 로컬 `tmp/public-prd-selector-review600-campfire-20260929`, `tmp/public-prd-selector-review600-reason-campfire-20260929`에 plan/results/summary만 있다. 저장 함수는 키·문서 전체 포함 시 쓰기를 거부한다.
- plan/results/summary SHA-256 앞 8자리: 첫째 `afe42b64/d5056885/17a8375c`, 둘째 `afe42b64/dfd694d9/ab1ad04c`.
- 이 자료는 이미 튜닝에 사용한 공개 PRD와 부분 정답이다. 독립 실사용 품질 및 Spring/Frontend의 확인 전 저장 금지 E2E는 미검증이다.
