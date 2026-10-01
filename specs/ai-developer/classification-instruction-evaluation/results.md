# U / U+C 실제 비교 결과

2026-10-01 · `feature/classification-instruction-comparison` · 실행 코드 `ac7b9ca`

## 결론

명확한 30개 기준에서 모델 오확정과 기존 gate 통과 오확정은 각각 **6→2건**이었다.
정상 정보 16개는 두 방식 모두 올바른 필드로 확정·보존됐고 정상 누락은 **0→0건**이었다.
그러나 오확정 4개는 모두 `other/confirmed → needs_confirmation`으로 옮겨갔다.
올바른 제외 판정은 0→1개, 필드·상태 불일치는 14→13개에 그쳤다.
**보류를 통한 오확정 감소는 관측됐지만 의미 분류 자체의 해결과 서비스 적용을 입증하지 못했다.**

별도 검토 항목 LS15는 U의 보류에서 U+C의 자동 확정으로 바뀌었다.
모호한 항목에 대한 위험 신호로 기록하며, 사전 합의대로 주 점수에는 넣지 않았다.
추가 호출·지침 수정·정답 수정·서비스 적용·큰 goal 재개 없이 이번 한 쌍으로 종료했다.

## 고정 조건과 실제 실행

- U: 기존 원문 단위 ID 선택 방식. U+C: U의 system 메시지에 승인된 일반 분류 지침만 추가.
- 원문 전체, 후보 앞뒤 240자 문맥, 모든 줄 단위 ID, 후보, 정답, 스키마와 속성 순서, 기존 gate 동일.
- `deepseek-ai/deepseek-v4.1-flash`, `https://integrate.api.nvidia.com/v1/chat/completions`.
- temperature 0, thinking false, 출력 상한 8,192토큰, 배치당 후보 8개.
- 문서 2개 × 방식 2개 × 배치 2개 = **실제 호출 8회**, 재시도 0, 실패 0, 미실행 0.
- FR은 U→U+C, LS는 U+C→U 순서. 각 방식·문서 1회분이며 반복 통계는 없다.
- 무료 근거는 현재 계정에 대한 사용자 확인 기록이다. 기록의 모델·엔드포인트·유효기간을 매 호출 전 검증했다.
  2026-10-01 17:32:45 UTC 만료 전 호출했고 무료 한도 거절은 없었다.
  계정 청구 화면이나 남은 quota를 독립 조회한 것은 아니며 청구액을 감사한 결과도 아니다.
- 지침·정답·원문·후보·실행 코드 등 155개와 freeze 자체, 총 156개 해시 일치.
  이전 Q/U 기준선 140개 해시도 일치. 저장된 실제 요청의 차이는 승인 지침 추가뿐이었다.

## 문서별 결과

수치는 **U → U+C**, 시간은 해당 문서의 2배치 실행 시간 합계다.
오확정·정상 누락·주 점수 보류는 명확한 30개만 집계한다.
인용 결함은 모호한 2개를 포함해 방식당 32개 모두 검사한다.

| 문서 | 모델 오확정 | gate 통과 오확정 | 정상 누락 | 주 점수 보류 | 인용 결함 | 시간(초) | 호출 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fluent Reader, 명확 15 / 정상 10 | 4→1 | 4→1 | 0→0 | 1→3 | 0→0 | 102.16→132.14 | 2→2 |
| LocalSend, 명확 15 / 정상 6 | 2→1 | 2→1 | 0→0 | 7→8 | 0→0 | 193.91→118.91 | 2→2 |
| 합계, 명확 30 / 정상 16 | **6→2** | **6→2** | **0→0** | **8→11** | **0→0** | **296.07→251.05** | **4→4** |

| 보조 지표 | Fluent Reader | LocalSend | 합계 |
|---|---:|---:|---:|
| 전체 보류, 모호한 사례 포함 | 2→4 | 8→8 | 10→12 |
| 모호한 사례의 보류 | 1→1 | 1→0 | 2→1 |
| 정상 정보 보존 | 10/10→10/10 | 6/6→6/6 | 16/16→16/16 |
| 정상 정보의 보류 | 0→0 | 0→0 | 0→0 |
| 정답에 맞게 제외 | 0→1 | 0→0 | 0→1 |
| 명확한 사례의 필드·상태 불일치 | 5→4 | 9→9 | 14→13 |
| 후보 보존 | 16/16→16/16 | 16/16→16/16 | 32/32→32/32 |

고정 지표에서 모델 오확정은 **실제 Profile 필드에 잘못된 `confirmed`를 붙인 것**이다.
`other/confirmed`는 Profile에 확정할 필드가 없어 이 오확정 수에는 들어가지 않지만,
정답 `other/irrelevant`와 다르므로 필드·상태 불일치와 보류로 드러낸다.
인용 결함 0은 유효한 원문 단위를 선택하고 후보 범위를 덮었다는 뜻이다.
의미 역할의 정확성이나 상충 근거를 빠짐없이 선택했다는 뜻은 아니다.

## 바뀐 판정과 남은 오확정

`supported`는 이번 실험의 기존 gate 통과 상태이며 사용자 직접 확정이나 Spring 저장 완료를 뜻하지 않는다.

| 사례 | 원문 후보·관계 | U | U+C |
|---|---|---|---|
| FR01 | Windows 10, 지원 환경 | deployment / confirmed / supported | other / confirmed / needs_confirmation |
| FR02 | Linux, 지원 환경 | deployment / confirmed / supported | other / confirmed / needs_confirmation |
| FR03 | modern UI 설명 | features / confirmed / supported | other / confirmed / needs_confirmation |
| FR13 | Paypal, 기부 링크 | other / confirmed / needs_confirmation | other / irrelevant / excluded |
| LS11 | Play Store, 배포 경로 | external_integrations / confirmed / supported | other / confirmed / needs_confirmation |
| FR07 | Google Reader API, 호환 API 규약 | external_integrations / confirmed / supported | 동일, 오확정 잔존 |
| LS10 | Weblate, 개발 기여용 번역 도구 | external_integrations / confirmed / supported | 동일, 오확정 잔존 |

정상 외부 연동 Inoreader·Feedbin, 다크 모드·OPML·검색·구독 정리·자동 규칙·알림,
파일/메시지 공유·휴대용 설정·트레이 시작·CLI 전송 기능, React·Flutter 및 프로젝트 정보는 모두 유지됐다.
정상 기능/연동 대조 12개도 모두 유지됐다.
한편 LS07의 명시적 자동 업데이트 부정은 두 방식 모두 `other/confirmed`로 보류돼 정답에 맞게 제외되지 않았다.
전체를 보류하는 결과는 아니지만, 명확한 사례의 불필요한 보류가 **8→11건** 증가했다.

## FR16·LS15 별도 판정과 근거

두 사례의 정답 초안과 주 점수 제외 여부를 실행 이후 바꾸지 않았다.

### FR16: 다른 RSS 서비스 추가 지원

- U·U+C 모두 `features / tentative → needs_confirmation`.
- 둘 다 FR 원문 42줄, 위치 `[2122, 2234)`를 선택했다.
- 원문: `Support for other RSS services are [under fundraising](https://github.com/yang991178/fluent-reader/issues/23).`
- 추가 지원은 모금 중이라는 근거로 보류했다. 별도 counter 단위 선택은 두 방식 모두 0개.
- 미정인 지원 범위와 기능 단위를 사람이 결정해야 한다. 주 점수 제외를 유지했다.

### LS15: 모든 데이터가 HTTPS로 전송된다는 표현

- U: `other / confirmed → needs_confirmation`.
- U+C: `features / confirmed → supported`.
- 둘 다 LS 원문 142줄, 위치 `[7712, 7961)`만 지지 근거로 선택했다.
  이 줄에는 `All data is sent securely over HTTPS`와 장치별 인증서 생성 설명이 있다.
- 원문 230줄의 속도 문제 해결 안내에는 `Disable encryption on both devices`가 있다.
  원문 전체와 줄 단위가 양쪽에 제공됐지만 **두 방식 모두 이 줄을 counter 근거로 선택하지 않았다**.
- U의 보류는 `other`에 따른 gate 결과다. 상충 설명을 인식해 보류했다는 증거는 없다.
- U+C는 절대적 암호화 표현을 확정했으므로 추가 사람 검토가 필요하다.
  사전 제외 항목이므로 확정적인 오답으로 재채점하거나 주 점수에 사후 편입하지 않았다.

## 검증과 미검증

- **고정 응답 로컬 테스트**: 신규 13개 통과. 최종 전체 1,354개 실행, 1,347개 통과, 7개 skip, 실패 0.
  요청 동등성, 8회 상한, 실패 중단, 각 지표 분리, 누락된 사용량 보고를 검사했다.
  이 테스트 수치는 모델 성능 수치가 아니다.
- **실제 모델 평가**: 위의 8회다. 원시 응답, 요청, 파싱 결과, 검증 결과를 모두 보존했다.
- 후처리 감사에서 원시 응답과 파싱 결과 일치, 8개 시작/반환/종료 기록, 지표 독립 재집계 일치를 확인했다.
- 고정 지침에는 이번 평가 문서명·제품명·사례 ID나 정답 맞춤 예시가 없다.
  결과를 본 뒤 지침·정답·gate·평가 기준을 수정하지 않았다.
- 두 문서에서 미리 고른 32개 후보의 분류 비교다. 문서의 모든 정보 추출 능력, 새 문서 일반화,
  반복 안정성, 전체 서비스 경로, 사용자 확인과 실제 Spring 저장, 배포 성능은 미검증이다.
  시간은 한 번의 순차 실행 실측이며 속도 개선의 반복 검증 결과는 아니다.
- 관계 검증기·추가 모델 단계·서비스 적용은 0. 큰 goal은 paused 유지.

## 기록 위치

- 상세 수치·32개별 판정·인용 ID: `specs/ai-developer/classification-instruction-evaluation/results.json`.
- 원시 기록: `E:/AgentFit/output/classification-instruction-v1/`.
  `freeze.json`, `approval.json`, `package.json`, `summary.json`, `verification.json`, `postcheck.json`, `calls/`.
- 최종 테스트 로그: `E:/AgentFit/output/classification-instruction-tests-final.log`.
- 실행 기록: `work/harness/classification-instruction-evaluation/EXECUTION.md`.

이번 승인 범위는 완료했다. 추가 반복, 수정, 서비스 적용은 진행하지 않고 종료한다.
