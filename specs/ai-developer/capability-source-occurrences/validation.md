# 구현 검증

## 변경

- 기능 인용만 받는 `extract_capability_candidates` 추가. 원문 정확 일치의 모든 위치를 기존 함수로 확장하고 문맥별 분류를 유지한다.
- `analyze_integrated_candidates`·`analyze_nvidia_candidates`에 `capability_candidates=False` 추가. true일 때만 동작 추출을 교체한다. 공개 HTTP/기본 분석 설정은 유지한다.
- 독립 추출7개 테스트 RED(구현부재)→GREEN, 통합8개 테스트 RED(옵션부재)→GREEN. 의미 판단은 가짜 모델 응답을 사용했으며 실제 모델 품질 검증과 구분한다.

## 실제 실행한 로컬 gate

| 그룹 | 결과 | 시간 |
|---|---:|---:|
| unit | 1215통과,6 Windows skip | 65.068초 |
| runtime | 35통과 | 123.916초 |
| contract | 36통과 | 6.696초 |
| core flow | 8통과 | 27.465초 |

최종 리뷰 수정 후 총1294통과/6skip, 모두 exit0, 그룹당180초 상한. 외부 API 호출0. 공유Python의 prefix 경고와 기존 잘못된 CLI 입력 검증의usage 출력이 있었으나 실패0이다. 로그는 이 계획의 `.superpowers/sdd/plan-capability-source-occurrences`에 보존한다. [리뷰](review.md)의 전송 선택 오류를 회귀2개 RED→GREEN으로 수정했으며 신규 테스트는 합계17개다.

## 남은 검증

최종 독립 리뷰1회와 Important1건 수정·전체 재검증을 완료했다. push/CI 및 실제3문서 비교는 아직 미완료다. 새로운 실제 기획서 일반화, 사람이 검토한 의미 정답, 사람 수정량/검토시간, 실제 Spring/운영 검증은 계속 미완료다. 이 기록은 모델 정확도나 전체 실사용 목표 달성을 의미하지 않는다.
