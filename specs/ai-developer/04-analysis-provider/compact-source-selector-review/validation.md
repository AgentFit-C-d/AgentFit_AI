# 간결 의미 검토 검증 기록

## 구현 검증

- 원문 선택자 분석기에 opt-in 간결 의미 검토를 연결했다. 정상 이슈는 기존 의미 수정으로 전달하고 잘못된 대상 ID는 `SEMANTIC_REVIEW_INVALID`로 보류한다. Solar/NVIDIA의 전송 경로를 각각 모의 검증했다.
- 평가 CLI는 간결 검토에서 실제 4,096 출력 토큰 상한과 `medium`/`low` 설정을 계획에 기록한다. 기본 분석기와 공개 Profile은 바꾸지 않았다.
- 전체 `python -m unittest discover -s tests -q`: 623건 통과.
- 기능 커밋 `f9a46bb`을 `feature/compact-source-selector-review`에 push했고 Linux CI `36539279165`가 성공했다. CI는 분석 정확도 합격을 뜻하지 않는다.

## 실제 문서 1건 탐색 실험

이미 튜닝에 사용한 Campfire PRD를 동일한 부분 정답 7개로 각각 한 번 평가했다. 모델 응답이 실행마다 달라 설정 변경의 인과 효과로 해석하지 않는다.

| 검토 설정 | 결과 | 부분 정답 | 검토 출력 | 경과 |
|---|---|---:|---:|---:|
| 간결 `medium` | 확인 필요, `INCOMPLETE_RESPONSE` | 7/7 | 4,096/4,096 | 47,876ms |
| 간결 `low` | 확인 필요, `INCOMPLETE_RESPONSE` | 7/7 | 4,096/4,096 | 46,479ms |

두 실행 모두 의미 검토가 출력 한도에 닿아 응답을 완성하지 못했다. `medium`은 최초 core 근거 오류를 한 번 수정한 뒤 검토에 도달했고, `low`는 최초 core·features 검증을 통과했다. 각각 정답 밖 값 30개는 사람 검토 전이다. 자동 완료는 둘 다 0건이다. 5건 확대 조건을 충족하지 못해 확대하지 않았고 기본값으로 승격하지 않았다.

## 산출물과 한계

- 무시된 로컬 폴더 `tmp/public-prd-compact-selector-campfire-20260929`, `tmp/public-prd-compact-selector-low-campfire-20260929`에 plan/results/summary만 저장했다. 평가 저장 함수는 실제 키와 문서 전체가 포함되면 기록을 거부하며, 응답 원문·Profile을 기록하지 않는다.
- plan/results/summary SHA-256 앞 8자리: `medium` `1714fba5/5456790b/017586c1`, `low` `c9865486/79055aea/d99b0122`.
- 모델의 간결 응답 `issues=[]`를 서버가 10개 필드 확인 완료로 정규화하므로, 출력이 완성되는 후속 실험에서도 오확정 검증이 필수다. 출력 상한 문제가 반복돼 검토 범위를 좁히는 별도 구조 실험이 필요하다.
- 이미 튜닝한 공개 PRD와 부분 정답만으로 서비스 품질을 증명할 수 없다. 새 독립 문서 및 Spring/Frontend의 확인 전 저장 금지 E2E가 남아 있다.
