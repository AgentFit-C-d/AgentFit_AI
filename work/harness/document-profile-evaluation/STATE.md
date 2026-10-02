# Document Profile Evaluation — 의미 검토 효과 오프라인 분석 완료, 종료

## 2026-10-02 의미 검토 효과 분석

- 사용자 범위: 이번에 저장한 AgentFit 단일 평가 기록만 사용한 분석·수정 계획. 새 모델 호출/재시도/분석 로직 수정/서비스 적용 없음. 큰 Goal 일시중지 유지.
- classified→review_completed의145후보 전수 대응. confirmed33 중 유지27·제외6, 새 tentative0. 미검토112 상태 유지. 기능 정리 curation=null/호출0, 후속 label 동일. 최종 Profile=projected,27긍정 위치 모두 보존, GitHub 동일 값만 합쳐26값.
- 중복 제거한 효과: 실제 오답 제거0, 놓친 오답1(Codex). 정상 의미 손상4: PDF/Markdown은 기존 대체 후보로 보류2, 재접속 유지·정보 부족/호환 후보 없음 처리 누락2. 역할/업무 수집 추가1건은 기존 사람 검토 판정 유지.
- GLM 입력23–25에는 전체 원문이 정확히 포함됐고, 후보23–24 앞뒤 문맥도 원문과 일치. 이유 코드는 not_current2 / not_product_fact2 / insufficient_evidence2. 통과 이유·내부 추론은 미확인.
- 실제 시간: 전체1762.135초, 모델 요청25회 합계1760.590초. GLM 검토3회768.533초(43.6%). 검토50% 단축은 단순 계산으로384.266초 절감/전체1377.868초이며 재실행 결과가 아님.
- 추천: 검토 불일치를 irrelevant로 바꿔 명시 확인 대상에서까지 빠뜨리는 경계를 우선 개선. 원시 분류/원문/거절 이유는 보존하고 보류 경로로 연결하는 수정·최소 회귀6그룹 계획만 작성. Codex 관계 오류는 이 수정으로 해결된다고 주장하지 않음.
- 변경 문서: specs/ai-developer/document-profile-evaluation/review-effect-analysis-20261002.md, review-effect-plan-20261002.md, 이 STATE. 원본 결과 폴더는 해시 보존, 별도 E:/AgentFit/output/document-profile-review-effect-20261002에145후보 대응표·검토 입력/응답·의미 영향·시간·해시·검증 요약 생성.
- 로컬 검증: 후보145개/검토33개/변경6개,40의미의 기존 인용, 원문 문맥 일치, 검토→기능정리 label 불변, 투영→최종 Profile 동일성, 원본 파일 해시 불변을 검사했다. 모델 재실행/개선 코드 테스트는 하지 않음.
- 남은 미확인: 검토가 옳게 제거한 오답 대조 사례(이번0), 모델 내부 원인, 검토 축소/제거의 전체 성능, 실제 UI 확인/저장 및 다른 문서 일반화. 기존 애매한 의미2개 판정도 유지.
- 종료 지점: 보고·최소 수정 계획까지 완료. 구현·추가 실험 없이 종료하며 큰 Goal을 재개하지 않는다.

## 2026-10-02 단일 실제 평가 승인

- 현재 사용자가 AgentFit 문서 1개, integrated-nvidia 경로 1회 실행을 승인했다. 이전에 사용자가 무료로 확인한 NVIDIA endpoint와 DeepSeek/GLM만 사용한다.
- 코드 기준 `274ec06`, 원문·골드·모델·지침·판정 고정. 기존 후보 주입 없음.
- 실행 제한: 실제 요청 최대 50회, 전체 1800초, 요청당 최대 600초와 남은 시간 중 작은 값, 재시도 0, 첫 실패 중단.
- 실행 전용 도우미 `E:/AgentFit/tmp/document_profile_live_once.py`: 기존 worker와 관측 재사용. 분석 코드 변경 없이 하위 요청 프로세스에 시간 제한을 적용하고 중간 관측을 체크포인트로 남긴다. 로컬 제한 테스트 4건 통과.
- 결과 폴더 예정: `E:/AgentFit/output/document-profile-baseline-live-20261002-v1`.
- 후속 작업: 실제 결과와 고정 골드의 수동 의미 대응·채점 후 보고하고 종료. 자동 수정·추가 실험·서비스 적용·큰 goal 재개 없음.

### 실제 실행 및 안전한 종료 기록

- 단일 실행 완료: DeepSeek 22회 + GLM 3회 = 실제 요청 25회, 재시도/호출 실패 0회. 1762.135초(29분22초). 마지막 요청은 남은451.520초에 제한449.520초로 축소되어 413.439초에 반환.
- 결과 `needs_confirmation`, 10개 필드 모두 unresolved. Profile의 실제 값은 project_name/domain=null, project_type=웹 서비스, 나머지 미정 기술5필드=null, 기능23표현, 외부연동=GitHub/Codex.
- 정상40의 수동 의미 대조: 보존26·보류9·누락3·사람 검토 필요2. 기능36만 보면 보존24·보류7·누락3·검토2. 목록 수와 의미 수는 별도.
- 최종 긍정 값 오분류 1건: 지원 Client Codex를 external_integrations로 포함. 최초 의미 분류에서 발생했고 GLM 검토에서도 유지. 사용자 확정/DB 저장은 실행하지 않았음.
- 누락3: 텍스트 입력(위치 연결), 재접속 유지·정보 부족/호환 후보 없음 후속 안내(의미 검토). 의미 대응 애매2: 역할·업무 수집, Catalog 검토. 전체 채점 완료 플래그는 false로 유지.
- 정상 의미 최초 불일치 확인분: 위치 연결1·의미 분류7·의미 검토4. 애매2는 원인 집계를 확정하지 않음. 인용 결함은 후보 사건 기준31(동작 anchor15, 분류 인용/등장순서12, 후보를 포함하지 않는 인용4).
- 원문·골드·분석 코드·지침·스키마 해시 전부 유지, trace 관측 오류0. 수동 대응표 재채점 결과 일치,40/36분모·모든 인용 위치·인증 키 미포함 확인.
- 결과 문서: `specs/ai-developer/document-profile-evaluation/live-baseline-20261002-report.md`. 원시 결과/trace/정답/동결/요청기록/수동 대응/채점은 `E:/AgentFit/output/document-profile-baseline-live-20261002-v1`에 보존.
- 남은 미검증: 애매한 의미2와 중간 상태 주장3의 사람 판정, 운영 HTTP 배포·실제 Spring 저장·새 문서 일반화. 이번 승인 범위 밖이며 실행/수정하지 않음.
- 현재 중단 지점: 결과 보고 및 기존 feature 브랜치 기록 보존 후 종료. 추가 모델 호출·자동 수정·서비스 적용·큰 goal 재개 없음.

## 2026-10-02 후속 승인

사용자가 제시한 기대값(10필드, 36개 세부 기능 의미)을 승인하고 현재 서비스 경로의 관측·채점 최소 구현과 로컬 검증을 요청했다. U/US 삽입과 실제 모델 호출은 금지. 브랜치는 `feature/document-profile-baseline`, BASE는 `db76596`.

- Task 1: 기대값의 내용은 유지하고 승인 상태·의미 단위 ID만 고정한다.
- Task 2: 기존 CandidateTrace/analysis_worker를 재사용하고 누락된 상세 단계만 opt-in 기록한다.
- Task 3: 수동 의미 대응표와 실제 기록을 대조하는 채점기를 구현한다. 문자열/목록 수로 대체하지 않는다.
- Task 4: 모델·호출 수·시간 상한을 보고하고 실제 호출 전에 종료한다.
- Pre-flight: 추출 입력은 원문만, 채점기는 골드와 기록만 받는다. 공개 API와 worker 출력 계약은 유지한다.
- Ruling: 기존 observer는 정확히 네 단계만 허용하므로 새 상세 기록은 별도 선택형 detail_observer로 추가한다. 기존 관측 소비자를 깨뜨리지 않기 위한 최소 확장이다.
- Ruling: Windows의 기존 기록 관례에 맞춰 이 STATE를 실행 ledger로 사용한다. 기존 `.superpowers` 내용은 수정하지 않는다.
- Baseline: `python -m unittest discover -s tests -p test_candidate_analysis_pipeline.py -q` → 20 passed.

### 현재 완료·검증

- Task 1 complete: `gold-draft.json`은 내용 변경 없이 유지. baseline-contract.json에 사용자 승인과 골드 SHA 기록, meaning-units.json에 기능 36 + 기타 4 의미 ID 생성.
- Task 2 complete: 기존 CandidateTrace와 실제 analysis_worker 재사용. 추가 상세 관측만 선택형 훅. 신규 테스트 5개 RED→GREEN, 실제 SDK/HTTP/child/loopback 테스트 3개 RED→GREEN.
- Task 3 complete: 수동 의미 대응표를 기록 해시와 묶어 최초 손실 단계와 최종 보존을 계수. 채점 테스트 12개 RED→GREEN. 미감사·미관측을 0오확정으로 만들지 않는 검증 포함.
- Ruling: 평가 기능은 diagnostic_tools에 두고 current worker를 그대로 재사용한다. 계획의 직접 함수 연결보다 서비스 경로 차이를 줄이면서 기본 서버에는 설치하지 않기 위함이다.
- Ruling: 대응표를 골드·trace 해시를 포함한 객체로 감쌌다. 다른 실행의 판단 재사용을 막기 위함이며 의미 기준은 그대로다.
- 최초 전체 unit: 1407건 / 1400 통과 / 7 skip, 77.972초. `E:/AgentFit/tmp/document-profile-unit-tests.log`.
- 리뷰 후 최종 전체 unit: 1410건 / 1403 통과 / 7 skip, 80.385초. `E:/AgentFit/tmp/document-profile-unit-tests-final.log`.
- 전체 runtime: 39건 통과, 151.673초. `E:/AgentFit/tmp/document-profile-runtime-tests.log`. 외부 API가 아닌 합성 응답·로컬 루프백이다.
- 실제 문서 준비 출력: `E:/AgentFit/output/document-profile-baseline-preparation-v1` (원문/추출문/준비 메타데이터/미실행 대응표). 36개 의미 모두 unjudged, 최종 누락 수 null.
- SDK 로컬 분할: LangExtract 1.7.0 / RegexTokenizer / max_char_buffer=4000 → 2 chunks. 모델 호출 0회.
- 제안 호출 수: 4 + ceil(N/8) + ceil(C/20) + K(0~4), 후보 상한 240에서 계산상 최대50회. 서비스 제한64회/1800초/호출당600초/재시도0.
- 독립 리뷰: Important 2건(미관측 지표가 0으로 표시됨, 중간 단계 미검토를 완료로 처리함). 3개 회귀 테스트가 수정 전 실패하고 수정 후 통과. 최초 오류 귀속과 전체 검토 완료 조건을 분리하고 지표별 관측 여부를 검사했다. 추가 모델 호출 없음.
- 초기 미실행 미리보기는 보존했다. `trace-preview-not-executed-v2.json`, `alignment-preview-not-executed-v2.json`, `metrics-not-executed-v2.json`을 별도 생성해 미관측 지표를 null로 표시했다.
- Task 4: local-implementation.md에 단계별 모델·호출식·제한을 기록했다. 다음 실제 실행 전에 승인·무료 조건 확인 및 기존 부모 프로세스의 제한 연결이 필요하다.
- 안전한 중단 지점: 로컬 구현·검증 완료. 이번 변경만 커밋/push한 뒤 결과 보고하고 종료한다. 실제 모델 평가·서비스 적용·큰 goal 재개는 수행하지 않는다.

아래는 이전 준비 단계의 기록이며 후속 승인이 실행 범위를 갱신한다.

## 현재 요청

실제 기획 문서 1개로 10개 Profile 필드의 기대값 초안과 문서 입력→새 후보 추출→의미 분류→최종 Profile 평가를 준비한다. 기존 모델 비교 추가 호출은 중단한다.

## 제한

- 새 모델 호출 0회, 서비스 코드 변경 0건, 배포·Spring 연결·큰 goal 재개 없음.
- 기존 후보를 입력에 주입하지 않음. 평가 정답·단어 예외를 모델 입력에 넣지 않음.
- 기존 결과, 다른 작업의 dirty 파일과 큰 goal 중단 상태 유지.

## 확인한 사실과 결정

- AgentFit 기획서 `E:/AgentFit/Docs/project-proposal.md`, SHA-256 `9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451`, 186줄/7,796 code points. 작업 트리의 같은 문서와 바이트 일치.
- 기존 개발 문서이므로 독립 일반화 검증 자료가 아님. 연결된 PRD나 대화의 스택 사실은 포함하지 않음.
- 조사 코드 기준 `16c024954c77c4d7171fb83475221d8a01d150d5`, 준비 브랜치 `feature/document-profile-evaluation-plan`.
- 필드 초안: 명시됨 5, 미정 5, 필드 전체 명시적 없음 0. 부분 기능·권한의 명시적 부정은 별도 기록.
- 기능 초안 16묶음/36개 의미 단위, 비기능 긍정 사실 4개, 문맥 점검 항목 16개.
- 실제 코드의 integrated-nvidia 경로는 semantic_assessment=True. 배포 모드는 미확인이고 기본 코드 모드는 default. 최근 모델 비교 지침이 서비스에 적용됐다고 가정하지 않음.
- 기존 observer만으로 원시 추출·대표 기능 선정의 모든 손실을 구분할 수 없어 향후 관측 보완을 계획함. 이번에 구현하지 않음.

## 변경 파일

`specs/ai-developer/document-profile-evaluation/`의 spec.md, plan.md, expected-values-draft.md, gold-draft.json, expected-profile-draft.json, preparation-validation.json 및 이 STATE.md.

한 번 사용한 로컬 문서 작성 도우미는 `E:/AgentFit/tmp/prepare_document_profile_gold.py`이며 앱·평가 실행 코드는 아니다. Git에는 평가 자료와 상태 파일만 포함한다.

## 검증

- 원문 바이트 해시, 두 위치 문서 일치, 인용 98곳의 Unicode 위치·문자열 일치 확인.
- 기존 `validate_profile`/`check_profile_snapshot`로 기대 Profile 초안의 형식·근거 검증 통과. 의미 정답이 사용자 승인됐다는 뜻은 아님.
- 신규 모델 호출 0회. 실제 추출·분류 품질 수치 없음. 앱 테스트 및 네트워크 모델 평가 미실행(문서 준비만 수행).

## 남은 작업과 중단 지점

1. 사용자가 10개 필드 및 세부 의미 초안을 검토하면 골드 동결.
2. 별도 승인 후 평가 전용 관측·채점 도구 구현과 합성 응답 테스트.
3. 실제 호출은 그때 무료 조건과 별도 호출·시간 상한을 확인하고 허가받은 범위에서만 수행.

현재 상태: **평가 준비 완료, 기대값 초안 검토 대기, 실행하지 않고 종료**.
