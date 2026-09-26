# Solar Mini 4 평가

## 조건
- 요청 solar-mini4; 관측된 응답 solar-mini4-260922.
- Pro4 section-v2와 입력7개·프롬프트·정답 기준의 해시 일치를 호출 전 확인. 모델만 변경했다.
- 추출/통합 none·4096토큰, 검토 medium·8192토큰, 최대6회·60초 그대로.
- Pro4는 직전 보관 결과와 비교했다. 동시 교차 실험이 아니며 모델별1회/사례로 일반 우열은 판단할 수 없다.
- 실제 문서2개는 이전 사용자 전송 승인을 사용했다. 전체 Profile과 원문은 이 보고서에 포함하지 않는다.

| 사례 | Pro4 | Mini4 | Pro4 ms | Mini4 ms |
|---|---|---|---:|---:|
| ROLE-001 | SECTION_CANDIDATE | SECTION_CANDIDATE | 21000 | 4359 |
| ROLE-002 | PROVIDER_TIMEOUT | SECTION_CANDIDATE | 40188 | 3047 |
| ROLE-003 | SECTION_CANDIDATE | SECTION_CANDIDATE | 11156 | 2781 |
| ROLE-004 | SECTION_CANDIDATE | SECTION_CANDIDATE | 9953 | 2359 |
| TEXT-SEM-004 | SECTION_CANDIDATE | SEMANTIC_REVIEW_INVALID | 1531 | 36125 |
| REAL-MABC-001 | SECTION_CANDIDATE | SECTION_COVERAGE | 28235 | 2813 |
| REAL-AGENTFIT-001 | INCOMPLETE_RESPONSE | SECTION_COVERAGE | 33578 | 15531 |

## 결과
- 두 모델 모두 정답0/7, 오답반환0, 오류7. Mini4는 추출오류6건·검토형식오류1건.
- 총 경과: Pro4 145.641초, Mini4 67.015초. Pro4 7호출, Mini4 9호출. 서로 다른 단계에서 실패했으므로 성공 분석 속도 비교가 아니다.
- Mini4 고정 수작업 후보8개 통합1회: 개발도구 포함 전부 selected, SECTION_MERGE. Pro4에서 확인했던 오류가 재현됐다.
- 일부 합성 실패 원본 검사에서 value_not_in_quote와 quote_resolution 오류를 확인했다. 이 검사는 전체 실패 원인의 완전한 분류가 아니다.
- 전체 단위168/168 통과. Mini 모델로6단계 호출과 실제 반환 모델명 기록을 테스트했다.

## 결론
Mini로만 바꿔서는 현재 추출 품질을 해결하지 못했다. 응답이 빨리 끝난 사례는 있지만 품질 개선 및 일반 속도 우위는 미입증이다.
기본 모델은 Pro4 유지. Mini는 SectionAnalyzer(key, model="solar-mini4") 또는 SolarAnalyzer(key, model="solar-mini4")로 명시해 실험할 수 있다. API키/.env 수정은 필요 없다.
추가 프롬프트 튜닝 없이 이번 비교를 종료했다. 다음에는 짧은 단일 인용/역할 판정 최소 실험으로 모델 능력과 출력 계약 부담을 구분할 필요가 있다.
