# Status 정의 통일 비교 결과

2026-10-02 KST · `feature/status-definition-unification` · 실행 기준 `6d106d2`

## 결론

**정의 통일로 other/confirmed는10→0건, 올바른 제외는2→11건이 됐다.
정상 정보16개는 모두 유지됐다. 그러나 모델·gate 통과 오확정은 각각2→3건으로 늘었고,
LS15는 상충 근거를 선택하지 않은 채 제외됐다. 안전한 자동 확정 개선에 성공했다고 판단할 수 없다.**

기존 U+C와 정의 통일 버전을 이번에 각각4회 새로 호출했다. 과거 결과를 새 기준선으로 대신 쓰지 않았다.
총8회·재시도0·실패0·미실행0. 결과 확인 후 지침·정답·코드·평가 기준을 수정하지 않았다.
서비스 적용0, 큰 goal paused 유지, 이번 한 쌍으로 종료한다.

## 무엇을 바꿨나

- UC: 과거 `classification-instruction-v1`의 실제 U+C 요청4개를 그대로 사용했다.
- US: UC system의 status 관련6개 구역만 `status-definition.txt`의 단일 정의로 통합했다.
  교체 범위는 `status-edits.json`에 고정했다. 역변환하면 UC system 전체가 정확히 복원된다.
- confirmed는 유효 출력 필드의 현재 대상 프로젝트 긍정 사실, other/irrelevant는 명확한 범위 밖,
  other/tentative는 필드 판단 불가로 정의했다. 명시적 부정은 해당 필드/negated,
  미정·해결되지 않은 상충은 tentative로 보존하도록 명시했다.
- 다른 분류 문장·스키마·모델·생성 설정·원문·32후보·정답·서버 gate·점수 함수를 유지했다.
  서버의 other/confirmed 보류를 일괄 제외로 바꾸지 않았으며 원시 field/status를 변경하지 않았다.
- 별도 실험 harness에만 연결했다. 기존 서비스 코드와 이전 freeze 파일을 수정하지 않았다.

## 실행 조건

- `deepseek-ai/deepseek-v4.1-flash`, NVIDIA `https://integrate.api.nvidia.com/v1/chat/completions`.
- 기존 temperature0, thinking false, max_tokens8192 및 출력 스키마 순서 동일.
- 양쪽 동일한 전체 원문, 후보 앞뒤240자, 모든 원문 줄 ID 제공. 배치8개, 문서별2배치.
- FR: UC→US, LS: US→UC. 2026-10-02 01:21:52~01:26:56 KST 실행.
- 무료 근거는 계정의 해당 모델·엔드포인트 무추가요금 및 한도 초과 거절에 대한 사용자 확인 기록이다.
  02:32:45 KST 만료 전 각 호출에서 유효성을 검사했다. 계정 청구 화면이나 잔여 quota 독립 조회는 미검증이다.
- 최대8회, 재시도0, 요청당600초, 전체5400초 제한. 실패·만료 시 전체 중단하는 기존 gate를 사용했다.

## 문서별 결과

수치는 **UC → US**다. 오확정·정상 누락·올바른 제외·주 보류는 명확한30개만 집계한다.
other/confirmed와 인용 결함은 전체32개 기준이며, 이번에는 other/confirmed 전부가 주 점수 대상이었다.

| 문서 | other/confirmed | 모델 오확정 | gate 통과 오확정 | 정상 누락 | 올바른 제외 | 주 보류 | 인용 결함 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fluent Reader, 명확15/정상10 | 3→0 | 1→1 | 1→1 | 0→0 | 1→4 | 3→0 | 0→0 |
| LocalSend, 명확15/정상6 | 7→0 | 1→2 | 1→2 | 0→0 | 1→7 | 7→0 | 0→0 |
| 합계 | **10→0** | **2→3** | **2→3** | **0→0** | **2→11** | **10→0** | **0→0** |

| 보조 지표 | UC | US |
|---|---:|---:|
| 정상 정보 보존 | 16/16 | 16/16 |
| 정상 정보의 보류 | 0 | 0 |
| 전체 보류, 모호한 사례 포함 | 11 | 1 |
| 명확한 사례의 필드·상태 불일치 | 12 | 3 |
| 원시 후보 보존 | 32/32 | 32/32 |
| 실제 호출 | 4 | 4 |
| Fluent Reader 시간 | 106.90초 | 44.97초 |
| LocalSend 시간 | 90.91초 | 60.66초 |
| 합산 실행 시간 | 197.80초 | 105.63초 |

인용 결함0은 원문 단위가 유효하고 후보 범위를 덮었다는 뜻이다. 의미가 맞거나 상충 근거가 충분히 선택됐다는 뜻은 아니다.
모델 오확정은 기존 정의대로 유효 출력 필드의 잘못된 confirmed다. other/confirmed를 오확정으로 사후 편입하지 않았다.
별도 지표를 함께 보여 해당 조합의 감소만으로 성공 판단하지 않는다. 시간은 한 쌍 실측이며 반복 검증 결과가 아니다.

## 실제로 바뀐 사례

- other/confirmed10개 중8개는 정답인 other/irrelevant/excluded로 바뀌었다.
  FR01·FR02 지원 환경, FR03 외관 설명, LS01·LS02 지원 환경, LS03 속도·신뢰성 설명,
  LS06 프로토콜, LS14 품질 설명이다.
- 나머지2개는 보류에서 **새 오확정**으로 바뀌었다:
  **LS05 REST API → backend/confirmed/supported**,
  **LS11 Play Store → external_integrations/confirmed/supported**.
- **LS10 Weblate**는 external_integrations/confirmed/supported에서 올바른 other/irrelevant/excluded로 바뀌었다.
- **FR07 Google Reader API**는 두 방식 모두 external_integrations/confirmed/supported 오확정이 남았다.
- 따라서 기존 오확정1개 해결, 신규2개 발생으로 합계2→3이다. 상태 조합 위반을 없애도 필드 분류 오류가 남거나 늘 수 있다.
- Inoreader·Feedbin 실제 연동, 정상 기능10개, React·Flutter 및 프로젝트 정보는 모두 보존됐다.

## LS07: 명시적 부정

두 방식 모두 **features / negated → excluded**였다.
원문64행 `[2598,2733)`의 “앱에 자동 업데이트가 없다”는 문장을 근거로 선택했다.
명시적 부정을 other/irrelevant로 바꾸지 않았고 원시 후보·field·negated·근거를 보존했다.

직전 과거 U+C에서는 이 사례가 other/confirmed였지만, **이번에 다시 호출한 UC도 이미 올바르게 판단했다**.
따라서 이번 한 쌍에서 LS07을 정의 통일로 개선했다고 주장할 수 없다.

## LS15: 상충 근거 선택과 불확실성 보존

주 점수에서 제외한 사람 검토 항목이며, 정답 초안을 바꾸지 않았다.

| 항목 | UC | US |
|---|---|---|
| field/status | features/confirmed | other/irrelevant |
| 서버 판정 | supported | excluded |
| 142행 HTTPS 전송 주장 선택 | 지지 근거로 선택 | 지지 근거로 선택 |
| 230행 암호화 해제 안내 선택 | 없음 | 없음 |
| counterUnitIds | 빈 배열 | 빈 배열 |

선택한142행 위치는 `[7712,7961)`, 선택하지 않은230행 위치는 `[12922,13127)`이다.
230행에는 `Disable encryption on both devices` 안내가 있다.
US의 제외는 모델 원시 응답에 직접 나타나며 서버가 변환한 결과가 아니다.
**상충 가능성을 검토한 뒤 tentative로 보존한 결과가 아니므로, 불확실성 처리 개선으로 볼 수 없다.**
이 항목을 올바른 제외11개나 정상 누락0개에 섞어 계산하지 않았다.
원시 후보는 보존돼 있지만 확인 필요 상태에서는 빠졌다. 안전한 보류 보존은 미해결이다.

FR16은 두 방식 모두 features/tentative/needs_confirmation으로 남았고, 추가 RSS 지원이 모금 중이라는42행을 선택했다.

## 검증·보존·한계

- 신규 고정 응답 테스트8개 통과: 요청 차이 제한, status 경계 변경 감지, 원시 판정·부정·보류 보존,
  LS15의 잘못된 counter와230행 구분, 실패 중단, live 재실행 차단.
- 최종 전체1362개 실행,1355개 통과,7개 skip,실패0,73.206초.
  고정 응답 테스트는 모델 의미 성능을 입증하지 않으며 위8회 실제 평가와 구분한다.
- 독립 코드 검토: Critical/Important/Minor0. 실제 성능·계정 quota는 코드 검토로 확인한 사항이 아니다.
- 사후 감사: freeze 자체 포함200개 hash, 이전 기준선140개 hash 일치. 실제8개 요청과 원본 응답·파싱 결과 보존.
  status 외 payload 동일성, 원시 field/status 보존, 별도 재집계 일치를 확인했다.
- 이번 비교는 같은32개 수동 선정 후보, 문서2개, 각1회분이다. 새 문서 일반화·반복 안정성·추출 누락·서비스/Spring 연결·배포는 미검증이다.
- 명시적 부정 유지와 정답인 제외 증가는 관측됐지만, 오확정 증가와 LS15 제외 때문에 서비스 적용 근거로 삼지 않는다.

### 검증 실행 이력과 판단

최초 전체 테스트는 repo root에서 잘못 실행해 test_analysis_diagnostics, test_analysis_timeout_comparison,
test_analysis_worker, test_anchored_candidates, test_anchored_prompt_revision, test_anchored_review_budget,
test_api_contract_probe, test_atomic_evaluation, test_atomic_verdict의 import 오류와
test_worker_memory.test_child_cannot_commit_more_than_its_limit 실패가 났다. 셸 종료코드 전달 오류도 있었다.
README의 ai_service cwd에서 다시 실행해 모두 통과했다. 이를 위해 제품 코드를 바꾸지 않았다.
보존 테스트의 최초 순서 가정 오류는 ID별 응답 동일성과 원문 후보 순서를 각각 검사하도록 수정했다.
독립 검토자는 기존 점수 정의를 변경 범위 밖으로 두었고, 사용자 지시에 따라 그대로 사용했다.

이전 freeze 보존을 위해 별도 harness를 사용하고 작업 기록은 기존 work/harness 관례로 유지했다.
재사용 gate/score를 수정하지 않았으며 미룬 검토 결함은 없다.

## 기록 위치

- 지침: `status-definition.txt`, 교체 명세: `status-edits.json`.
- 상세32개 판정·원문 근거·호출별 시간: 같은 폴더의 `results.json`.
- 원시 요청/응답·freeze·summary·verification·postcheck: `E:/AgentFit/output/status-definition-v1/`.
- 최종 로컬 로그: `E:/AgentFit/output/status-definition-tests-correct-cwd.log`.
- 초기 경로 오류 로그: `E:/AgentFit/output/status-definition-tests.log`.
- 실행 상태: `work/harness/status-definition-unification/STATE.md`.

실제 비교와 결과 보고를 완료했으며 추가 호출·튜닝·서비스 적용·큰 goal 재개 없이 종료한다.
