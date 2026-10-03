# 복구 테스트 버전 의존성 정리 결과

작성일: 2026-10-03. 기준 commit `10b8d02`, branch `feature/recovery-test-version-isolation`.

## 결론

과거 실행과 최신 코드가 다른 경우의 거부를 유지하면서, **동일 버전 복구 테스트를 보존된 코드의 별도 Python 프로세스로 옮겼다.** 테스트·오프라인 도구·문서만 변경했다. 서버의 tentative/proposed 수정, 지침 B, 모델·프롬프트·스키마·계약, 원본 fixture는 그대로다.

최종 전체 unit 회귀 1,504개는 **1,493 통과 / 실패 0 / 오류 0 / skip 7 / 예상 실패 4 / 예상 밖 성공 0**으로 끝났다. 과거 CODE_MISMATCH에 막혔던 11개를 포함한 기존 복구 20개는 모두 본래 assertion을 실행해 통과했고 skip은 없었다.

실제 모델 호출·외부 전송·실제 복구 재개·배포·Spring 저장은 모두 0이며 큰 Goal은 paused다.

## 1. 원인과 테스트 분리

기존 `test_review_recovery.py`가 사용하는 ROOT는 항상 현재 checkout이었다. 서비스가 변경되자 검사기의 `verify_runtime`이 올바르게 `CODE_MISMATCH`를 반환했지만, 같은 버전의 복구 동작을 검사하려던 테스트까지 이 지점에서 멈췄다.

수정 전에 다시 실행해 **20개 중 9 통과, 2 assertion 실패, 9 오류**를 재현했다. 실패/오류 11개는 다음과 같다. 모두 동일 버전에서 검증해야 할 조건이다.

| 기존 테스트 (`test_` 접두사 생략) | 실제 검증하려던 조건 | 수정 후 |
|---|---|---|
| saved_run_plans_only_first_failed_review_and_keeps_failed_response | 완료된 요청 1–23 재사용 계획, 실패 요청 24부터 검토, failed 응답 유지 | 통과 |
| synthetic_resume_does_not_transmit_completed_calls_or_export_profile | 기존 완료 요청을 합성 전송 목록에서 제외, 20/20/4 검토 후 범위 검사, Profile 출력 금지 | 통과 |
| first_additional_failure_stops_and_other_name_cannot_resume_again | 첫 추가 실패에서 중단, 다른 이름으로 중복 계획 실행 금지 | 통과 |
| partial_success_records_only_validated_checked_ids | 첫 묶음 20개만 검토 완료, 다음 실패 시 나머지 24개 미검토 | 통과 |
| invalid_success_reply_is_not_completed_review | 잘못된 후보 ID 응답은 성공 전송이어도 완료로 계산하지 않음 | 통과 |
| cumulative_time_not_reset_and_timeout_has_no_followup | 원본 소비 시간 포함, 잔여 시간 제한, 시간 초과 후 후속 요청 없음 | 통과 |
| stored_partial_review_reuses_success_and_resumes_second_batch | 부분 성공 사본에서 첫 검토 결과 재사용, 두 번째 묶음부터 합성 검사 | 통과 |
| mutated_plan_cannot_reset_budget_and_exhausted_limit_stops_before_send | 예산 변조 거부, 원본 24회로 한도 소진 시 추가 시도 없음 | 통과 |
| invalid_saved_review_cannot_be_reused_even_when_transport_succeeded | 저장된 검토 응답의 잘못된 ID를 재사용하지 않음 | 통과 |
| elapsed_cannot_be_reduced_below_retained_deadline_consumption | 기록 소비 시간 축소를 CONSUMPTION_MISMATCH로 거부 | 통과 |
| negative_recorded_cost_cannot_credit_the_original_budget | 음수 소비량으로 예산을 늘리는 기록을 CONSUMPTION_MISMATCH로 거부 | 통과 |

**현재 버전의 거부 검사**는 `CurrentRecoveryVersionTests`로 별도 분리했다.

- 실제 과거 기록 + 현재 코드 → 정확히 `CODE_MISMATCH`.
- 메모리에 현재 코드를 로드한 채 옛 snapshot 경로만 제시 → `LOADED_RUNTIME_MISMATCH`.
- 구 `tentative/proposed/excluded` 파생 decision → `INVALID_SEMANTIC_ASSESSMENT`.
- 같은 원시 A/B 응답을 현재 코드로 재판정 → 별도 결과만 생성, RelayWave의 `needs_confirmation` 확인.

## 2. 격리 방식

1. 기존 records.zip의 컨테이너 해시와 봉인 파일 208개의 개별 해시를 검사한다.
2. 새 임시 디렉터리에 파일을 복사한다. snapshot의 실행 파일 147개를 frozen hash와 비교한다.
3. 실제 실행 후에 추가됐던 복구 검사기 `diagnostic_tools/review_recovery.py`는 **현재 파일을 변경 없이** 별도 복사한다. 과거 실행에 포함돼 있었던 것처럼 표시하지 않는다.
4. 별도 Python 프로세스가 보존된 `agentfit_ai` 모듈만 로드한다. Python 바이너리·버전·의존성 및 모듈 실제 경로의 기존 검사를 그대로 수행한다.
5. 기존 20개 테스트 본문을 실행한다. 각 setUp에서 정상 runtime 검증을 먼저 통과한 다음 사본에 결함을 넣는다. 다른 부정 테스트가 선행 CODE_MISMATCH 때문에 잘못 통과하는 것을 막는다.
6. 자식 결과의 개수·테스트 이름 전체 집합·중복·종료 코드·runtime 경로·검사기 해시를 부모가 확인한다. 각 결과를 부모의 개별 테스트로 전달한다. 자식 20개를 총합에 중복 가산하지 않는다.

해시 검사를 끄거나 원본 seal을 현재 코드에 맞추지 않았다. 기존 테스트의 결함 주입·재봉인은 이전과 동일하게 **임시 사본만** 대상으로 한다. 현재 버전용 합성 실행 fixture나 실제 재개 기능은 새로 만들지 않았다.

자식은 분석 모듈 import 전에 소켓·DNS·추가 프로세스 전송 차단을 설치한다. API 키 환경변수를 제거하고 원본을 수정하지 않는다. 전체 suite의 로컬 HTTP/IPC 검사는 loopback만 허용한다. 부모 suite가 자식을 시작하는 것과 자식에서 실행하려는 외부 전송/프로세스 탈출을 구분한다.

테스트 내부 자식 실행은 `shell=False`로 절대 `sys.executable`을 사용한다. 개발 PC의 RTK를 CI 필수 의존성으로 추가하지 않는다. 직접 실행한 셸 명령과 로컬 기록용 실행기는 기존 RTK 규칙을 따른다.

## 3. 원본·기대값 보존

- 원본 records.zip SHA256: `59a2fd04d7d58fe1224371a58355d9f432b2307a0f8ef1cefaeabff11fcf79f3`.
- 원본 archive/manifest, 과거 응답·문서·골드·B 지침, 현재 서버/계약/복구 검사기 등 **보호 파일 370개가 바이트 기준으로 동일**함을 확인했다.
- 이동한 기존 **20개 테스트 메서드의 AST가 수정 전과 동일**하다. 원래 assertion·기대값·분기·예상 실패 표시를 변경하지 않았다. setUp의 유효 runtime 확인만 추가했다.
- 기존 조건에 없는 새 blanket skip이나 expectedFailure는 추가하지 않았다.
- 앞선 tentative/proposed 서버 수정 파일도 그대로 유지했다.

기록: `E:/AgentFit/output/recovery-test-version-isolation-20261003-v1/protected-before.json`, 같은 폴더의 `integrity-*.json`.

## 4. 파생 decision 버전 검사

동결된 D2 A/B 각각의 옛 파생 레코드는 현재 검사기에 거부된다. 같은 원시 응답은 새 코드로 정상 재검증된다. 각 A/B의 C006만 `excluded → needs_confirmation`이며 다른 원시 필드·의미 축·근거는 동일하다.

구 파생 파일을 별도로 보존한 뒤 새 파일을 `offline-current-code-reassessment`로 작성하고 구 파일 해시가 그대로인지 검사했다. 자동 마이그레이션은 하지 않았다. 이 검사는 새 모델 실행이나 새 정확도 평가가 아니다.

영구 검증 자료는 최종 전체 suite의 `cases-112704954176/*-raw-reassessment.json`에 있으며 원본 실험 폴더를 덮어쓰지 않았다.

## 5. 테스트 결과

같은 Windows Python 환경에서 실행했다. Linux GitHub CI나 다른 Python 바이너리의 실행 결과로 확대 해석하지 않는다.

| 범위 | 실행 | 통과 | 실패 | 오류 | skip | 예상 실패 | 시간 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 수정 전 복구 회귀 | 20 | 9 | 2 | 9 | 0 | 0 | 14.516초 |
| 수정 후 복구·버전 회귀 | 22 | 22 | 0 | 0 | 0 | 0 | 28.693초 |
| 전체 unit (launcher 수정 전) | 1,503 | 1,492 | 0 | 0 | 7 | 4 | 115.533초 |
| 최종 전체 unit | 1,504 | 1,493 | 0 | 0 | 7 | 4 | 137.515초 |
| runtime_tests | 39 | 39 | 0 | 0 | 0 | 0 | 147.251초 |
| core_flow_tests | 8 | 8 | 0 | 0 | 0 | 0 | 29.749초 |
| contract_tests | 47 | 47 | 0 | 0 | 0 | 0 | 7.554초 |

현재 최종 전체 unit에는 기존 복구 20개 + 버전/launcher 검사 3개 + 결과 전달 검사 1개가 포함된다. 이 24개는 전부 통과했다. 결과 전달 검사는 의도적으로 만든 테스트 실패·예외·subtest 실패·skip이 부모에도 정확히 반영되는지를 검사한다. 내부 sentinel 실패를 제품 회귀 실패나 모델 품질 결과로 계산하지 않는다.

이 검사를 추가하는 과정에서 새 전달 도구가 subtest 예외를 failure로 집계하는 문제를 실패 테스트로 확인했고, error로 구분하도록 수정했다. 해당 초기 실패 로그도 보존했다. 합격 조건 완화는 없다.

독립 리뷰에서는 자식 launcher가 RTK에 의존해 Linux CI에서 실패할 문제 1개를 찾았다. PATH를 비운 회귀로 FileNotFoundError를 재현한 뒤 Python 직접 실행으로 수정했다. 같은 조건에서 기존 20개를 실제로 실행하는 신규 검사와 버전 검사 2개가 **3/3 통과(26.714초)**했다. 이후 최종 전체 unit을 다시 실행했다. 후속 읽기 전용 리뷰에서 해당 지적 해결을 확인했고 추가 발견은 없었다. 실제 Linux CI는 실행하지 않았다. runtime/core-flow/contract는 해당 테스트 launcher를 사용하지 않으며 위 성공 결과를 유지한다.

### 남은 skip 7개

- `TraceWorkerTests.test_symlink_target_is_preserved_without_analysis`: 현재 플랫폼에서 symlink 생성 불가.
- `DoclingGroundingEvaluationTests.test_pinned_structured_cases_have_unique_page_gold`
- `DoclingGroundingEvaluationTests.test_structured_fixture_is_a_real_heading_and_table`
- `DoclingStructuredTrialTests.test_real_docling_model_preserves_header_footer_and_repeated_text`
- `DoclingStructuredTrialTests.test_real_standard_pipeline_converts_two_page_synthetic_pdf`
- `DoclingStructuredTrialTests.test_real_standard_pipeline_preserves_table_cells_and_heading`
- `FullCandidateGroundingTests.test_all_fixed_gold_positions_survive_real_docling_pdf`

뒤 6개는 기존 선택 Docling 의존성 부재다. 설치·다운로드는 이번에 수행하지 않았으며 해당 실제 변환 경로는 미검증이다.

### 남은 예상 실패 4개

`MentionRoleCauseTests`의 다음 기존 모델 역할 오류 사례는 그대로 남아 있다.

- `test_historical_v2_client_is_not_an_adopted_outside_provider`
- `test_historical_v2_target_name_meets_semantic_role_expectation`
- `test_historical_v3_client_is_not_an_adopted_outside_provider`
- `test_historical_v3_target_name_meets_semantic_role_expectation`

이번 테스트 구성 변경이 프로젝트명·지원 Client의 모델 오분류를 해결한 것은 아니다. **남은 예기치 않은 실패/오류는 0개**다.

## 6. 기록과 변경 파일

출력: `E:/AgentFit/output/recovery-test-version-isolation-20261003-v1/`

- 초기 실패: `tests-110734420718.txt`
- 격리 22개: `tests-111414741344.txt`
- 전달 오류 재현/수정: `tests-111616315078.txt`, `tests-111659693726.txt`
- RTK 없는 조건 재현/수정: `tests-112511553767.txt`, `tests-112548284692.txt`
- 중간 unit: `tests-111731243150.txt`
- 최종 unit: `tests-112704954176.txt`
- runtime: `tests-111730997491.txt`
- core flow: `tests-111730732340.txt`
- contract: `tests-111730197179.txt`
- 최종 자식 개별 결과: `cases-112704954176/*-preserved-results.json` (기본 격리 및 PATH 없는 실행 각 20개 성공)

변경 파일:

- `ai_service/tests/test_review_recovery.py`: 부모 개별 테스트 수집.
- `ai_service/tests/recovery_preserved_cases.py`: 기존 본문 이동 및 정상 시작 상태 확인.
- `ai_service/tests/recovery_version_fixture.py`: snapshot 검증·격리·결과 전달 준비.
- `ai_service/tests/recovery_preserved_worker.py`: 테스트 전용 자식 실행기. 서비스 복구 worker가 아니다.
- `ai_service/tests/test_review_recovery_versions.py`: 현재 버전의 거부·별도 재판정.
- `ai_service/tests/test_recovery_result_forwarding.py`: 실패/오류/skip 전파.
- `work/harness/recovery-test-version-isolation/`: 실행 로그·해시 감사 도구와 상태.
- `specs/ai-developer/recovery-test-version-isolation/`: 명세·계획·이 보고서.

기존 다른 작업 변경은 보존했다. 외부 전송 금지에 따라 로컬 commit만 하고 push하지 않는다. 실제 복구 재개·제품 코드 변경·큰 Goal 재개 없이 종료한다.
