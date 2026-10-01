# 직접 필드 판단 A/B 한 쌍 결과

2026-10-01. **18회 정상 반환·재시도0, 양쪽68개 완료. 부분 개선은 있으나 사전 기준 미통과.**
추가 반복·서비스 반영을 하지 않고 종료한다. 큰 goal은 paused 유지.

## 1. 동일 조건 및 무료 범위

- A: 기존 의미 축·mentionKind를 출력하는 분류기와 기존 서버 검증.
- B: 출력 field/status/support/counterEvidence를 직접 판단하는 평가 전용 분류기.
- 양쪽 모두 **동일한 저장 linkding 원문4558 Unicode code points 전체**, 후보68개,
  각 occurrence의 앞뒤240 code points(문서 경계에서는 가능한 만큼), 원래 순서·8개 묶음.
  마지막은4개. 원문/문맥에 대한 A/B user message는9묶음 모두 byte-equivalent.
- 같은 `deepseek-ai/deepseek-v4.1-flash`, NVIDIA endpoint,
  temperature0, thinking=false, max_tokens8192. A→B 각9회, 재추출·GLM검토·수정 호출 없음.
- 원문24개 기존 rejected 기록 보존. 승인 gold는 양성6개·음성4개이며 양쪽에 동일.
  gold/정답이나 이름별 예시는 prompt에 넣지 않았다. 정답 밖58개는 별도 진단.
- 기존 사용자 확인(현재 계정 무료 API 및 초과 시 자동 결제 없는 거절)과
  만료2026-10-01 17:32:45 UTC의 무료 기록을 매 호출 전 검증했다.
  계정 과금 내역/잔여량을 독립 조회하지는 않았다. 유료 전환·다른 모델·Luna 호출 없음.
- 실행 전후 source/코드/gold/요청/무료 기록 해시 모두 동일. 이 실험의 코드/정답을
  응답을 본 뒤 변경하지 않았다. 실제 서비스 `/internal/v1/analyze` 경로는 실행하지 않았다.

## 2. 같은 정답 기준의 실제 모델 결과

| 지표 | A 현재 분류 | B 직접 필드 |
| --- | ---: | ---: |
| 모델의 잘못된 confirmed 제안(유효 출력 필드, 정답10개) | 4 | 4 |
| 서버 통과 오확정 / 정답10개 | 4 | 3 |
| 정상 정보 누락 / 양성6개 | 4 | 2 |
| 정상 누락 사유 | 보류2·제외1·오필드1 | 보류1·오필드1 |
| 판단 보류 / 정답10개 | 2 | 3 |
| 정상 정보의 보류 / 양성6개 | 2 | 1 |
| 전체 판단 보류 / 후보68개 | 24 | 37 |
| 전체 supported 제안 | 16 | 31 |
| 전체 excluded | 28 | 0 |
| 기록 유실 / 후보68개 | 0 | 0 |
| 공통 Profile 변환 뒤 정상 누락 / 양성6개 | 4 | 2 |
| 실제 호출 시작 / 반환 / 제공자 실패 / 재시도 | 9 / 9 / 0 / 0 | 9 / 9 / 0 / 0 |
| 모델 호출 합계 | 962.895초 | 546.460초 |
| 방식 전체 경과 | 963.162초(16분03초) | 546.719초(9분07초) |
| 로컬 검증·변환 | 0.0035초 | 0.0011초 |

오필드는 오확정과 정상 누락에 동시에 해당할 수 있다. 합산 정확도 점수는 만들지 않는다.
`other/confirmed`는 실제 Profile 필드의 확정 제안이 아니므로 첫 행에서 제외하고 별도 모순으로
보존했다. 주 gold에서는 A JavaScript, B pytest가 이에 해당한다. B의 pytest는 보류됐다.
supported는 모델 제안의 서버 통과 상태이며 사용자 확인 완료가 아니다.

한 쌍의 관측상 B의 시간이 약43% 짧았지만, 순서·제공자 부하를 통제한 반복 통계는 아니다.

## 3. 주 평가10개 상세

| 후보 | 정답 | A | B |
| --- | --- | --- | --- |
| Firefox | 제외 | 외부 연동으로 오확정 | 동일 오확정 |
| Chrome | 제외 | 외부 연동으로 오확정 | 동일 오확정 |
| linkding | project_name | field는 맞지만 product_operation 역할과 모순돼 보류 | 올바른 확정 제안 |
| Django | backend | field는 맞지만 external_service 역할과 모순돼 보류 | 올바른 확정 제안 |
| JavaScript | frontend | 개발 문단의 non_product/other로 제외 | 올바른 확정 제안 |
| PWA | project_type | features 오필드 확정, 정상 필드 누락 | 동일 오류 |
| Internet Archive | external_integrations | 정상 | 정상 |
| Organize bookmarks with tags | features | 정상 | 제목만 인용해 occurrence 근거 부족으로 보류 |
| Clean UI optimized for readability | 제외 | features 오확정 | 동일한 잘못된 features 제안, 제목만 인용해 서버 보류 |
| pytest | 제외 | 정상 제외 | other/confirmed 모순으로 보류 |

**해석:** B는 중간 역할 분류에서 생긴 두 모순과 JavaScript 누락을 피했지만,
원모델의 잘못된 필드 확정 제안4개는 줄지 않았다. 서버 통과 오확정1개 감소는
Clean UI의 의미를 올바르게 제외해서가 아니라 근거 인용이 부실해 차단된 것이다.
같은 인용 결함으로 정상적인 태그 정리 기능도 새로 빠졌다.

## 4. 정답 밖58개 — 점수와 분리

방식명을 X/Y로 가린 공통 행과 원문으로 먼저 검토한 뒤 대응(X=B,Y=A)을 열었다.
검토자는 도구 작성 에이전트이므로 독립 사람 검토는 아니다. 사전 gold를 사후 확장하지 않았다.

- 양쪽 모두 `OIDC`를 외부 서비스 제공자로 확정했다. 프로토콜/표준과 제공자의 혼동이 남았다.
- A는 확장 URL 안의 `linkding` 조각(C014)을 features로 확정했다.
- B는 일괄 편집/메모/나중 읽기(C006), 북마크 공유(C007)도 `Feature Overview` 제목만
  인용해 보류했다. 주 점수 밖에서도 명확한 정상 기능 누락 위험2건이 추가 관찰됐다.
- B는 uv·ruff·djlint·prettier 같은 도구도 다수 other/tentative 또는 other/confirmed로 보류했고,
  최종 excluded가0개였다. 정상6개 보류는 줄었지만 전체 사용자 검토 부담은 늘었다.
- URL·반복 프로젝트명, 개발 절차의 Django, Node.js/Python, Docker/DevContainers,
  tag auto-completion의 범위는 기존 기준대로 사람 검토 필요. 정답으로 인증하지 않는다.

## 5. 판단과 검증 한계

**이 한 쌍은 사전 개선 가능성 기준을 통과하지 못했다.** Firefox/Chrome 오확정0 조건,
PWA 정상 필드 유지, 정상 대조 기능 보존이 충족되지 않았다.
중간 역할 출력을 줄여 정상 기술 정보를 복구한 신호는 있으나, B 그대로의 채택 근거는 부족하다.
다음 반복 여부는 사용자가 결정한다. 이번에는 후속 프롬프트 수정·호출·서비스 적용을 하지 않는다.

- 실제 모델 평가: 위 수치는 동결된 입력을 사용한 새로운 NVIDIA 응답18개에서 집계했다.
- 고정 응답 테스트: 비교 전용14개는 평가기·근거 검증·호출 제한·오류 중단 검증이다.
  이것을 실제 모델 정확도로 사용하지 않았다.
- 최종 로컬 suite:1303실행,1296통과,7skip(82.661초). skip을 통과로 세지 않았다.
- 독립 코드 리뷰 P2 오류 사유 손실1건을 RED→GREEN 테스트로 수정했다. 미해결 리뷰 지적 없음.
- 서비스 코드 변경 없음. `/internal/v1/analyze`, Spring 저장, 배포, 사용자 질문 UI는 미검증·미변경.
- linkding은 이미 개발에 사용한1개 문서다. 새 문서 일반화·반복 안정성·운영 정확도는 미검증.

## 증거 위치

- 실행 결과: `E:/AgentFit/output/direct-field-comparison-v1/summary.json`
- 원응답/요청/호출 시작·종료: 같은 폴더 `calls/`(각18개).
- 입력·정답·코드 동결: `freeze.json`, `inputs.json`, `payloads.json`.
- 실행 후 동일성 확인: `verification.json`(변경된 동결 파일0, user message9쌍 동일).
- 별도 출력 검토: `blind-review.json`, `blind-audit.md`, `blind-key.json`.
- Git용 요약: [results.json](results.json). 기존 자료와 이전 결과는 수정하지 않았다.
