# 고정 통합 분석의 독립 공개 문서 평가

## 목적과 권한

현재 통합 분석 전체가 새 문서에서 어느 값을 놓치거나 잘못 제안하는지 측정한다. 사용자는 실사용 목표 안의 설계·계획·구현·실험을 자율 진행하도록 승인했고 SDD와 feature별 push, 직접 순차 구현을 요청했다. 이번 기능은 평가 계약과 실행기이므로 architectural 경로로 명세·계획을 남긴다. 기본 서비스·모델·프롬프트는 바꾸지 않는다.

## 발견된 자료 문제와 선택

예약된 PUBLIC-04는 이미 사용한 Immich와 SHA256이 같다. PUBLIC-05는 사용한 Actual Budget과 같은 프로젝트 계열이다. 예약 manifest의 seen=false를 신뢰해 독립 표본에 포함할 수 없다. 두 문서를 제외하고 다른 공식 저장소 문서 PUBLIC-11/12로 교체한다. 원래 manifest/문서는 보존한다.

1. 채택: 현재 통합 경로를 먼저 고정하고 공개 10문서의 사전 정답을 작성한 뒤 3회씩 실행한다. 재현성과 노출 여부를 확인할 수 있다.
2. 기존 튜닝 자료를 반복하는 방식은 원인 회귀에는 유용하지만 독립 성능 근거가 되지 않는다.
3. 모델이 결과를 보고 정답도 만드는 방식은 판단 오류를 공유하므로 사용하지 않는다. 정답은 응답 전 소스 검토로 작성하고, 사람 검토 여부를 별도로 표시한다.

## 고정과 독립성

- 시작 코드:9af3f2a9bcd47d5e3bb40860fe674434787b442a. 통합모드 confirmation-v2, Solar 추출/분류, GLM5.3 검토, DeepSeek V4.1 Flash 동작/대표정리, 검토묶음20, maxcalls64/NVIDIA503retry1, 요청기한1800초를 고정한다.
- 본문을 읽기 전에 기존 production Python/requirements 파일의 LF 정규화 SHA256과 설정을 freeze.json에 기록한다. 새 평가기 코드는 별도로 커밋/해시한다. 실험 전후 고정 코드·입력·정답 해시를 검사한다.
- 공개 문서는 고정Git커밋·원본SHA256·UTF8/100000자·크기100000bytes로 검증한다. 이 크기를 벗어나면 자르지 않고 사전 부적합으로 기록한다. 다른 계열과 원문해시가 중복이면 제외한다. 이전튜닝 계열/해시와 대조한다.
- 사전학습 노출은 알 수 없다. 영어 제품README는 한국어 초기기획서·PDF 분포를 대표하지 않는다. 이 세트만으로 전체실사용 완료를 선언하지 않는다.

## 정답과 채점

- 문서별10필드를 소스에서 검토하고 의미 단위별ID, 허용되는 정확한 원문 구간 목록, 필드, 명시적 부재 여부를 모델응답 전에 고정한다. 동의 표현은 소스에 실제로 있는 구간만 사전 등록한다. 부정/검토안/타제품/개발용 오확정 위험 구간은 별도 exclusion으로 적는다.
- 원문·정답 인용·모델 Profile/응답은 Git이나 결과 파일에 저장하지 않는다. 공개 원문은 기존 ignored 로컬 자료 폴더에 보관하며 골드는 위치와ID만 저장한다. 코드포인트 위치는 검증된 원문을 기준으로 한다.
- 정확한 Profile/근거 검증 후 각 출력값이 증거 안에서 일치하는 원문 위치를 계산한다. 단일골드단위로 유일하게 매칭될 때만 인정한다. 같은 단위의 중복 출력은 중복오류, exclusion과 겹치는 정확한 등록구간은 명시적 오류다. 모호하거나 등록되지 않은 출력은 unassessed로 남긴다. 임의 동의어 확대/부분문자열 채점으로 통과시키지 않는다.
- 성공/확인필요/실패 전부 분모에 포함한다. 실패는 골드 전부 누락으로 기록한다. 전체 및 필드별 matched/gold, known_wrong, duplicates, unassessed, evidence_invalid, 질문/상태수, 지연을 보고한다. unassessed를 정답0오류0으로 숨기지 않는다. 이 자동일치 지표를 완전한 의미precision/recall이라고 부르지 않는다.
- 기록은 source/config/gold/evaluator hash,case/run,고정 enum·개수·시간·출력의 위치/해시만 포함한다. 모델 내용·키·예외문자열은 출력하지 않는다. 사람이 검토하기 전 human_reviewed=false/release_gate_passed=false다.
- 기존95%precision/90%recall·실패5%이하·근거100%·중대오류0·사람수정률10%이하·검토시간 기준은 유지한다. 사용자의 시간제한 유예에 따라 이번실험에서 지연은 기록하되 통과/실패 문턱으로 쓰지 않는다. 기존 draft-readiness v1의60초기준은 소급변경하지 않는다.

## 실행·실패·수용 기준

- 전용 feature/independent-profile-evaluation. 기존 isolated analysis-runtime checkout 사용.
- 독립성/해시/골드/설정 사전검증 오류는 API전에 중단한다. 키는 기존 로컬.env에서 메모리로만 읽고 요청worker stdin으로 전달한다.
- 실제 서비스와 같은 execute_integrated_analysis를 요청별 프로세스로 실행한다. 전체기한1800초,종료후 다음사례 진행. 부분생성 결과를 저장하거나 성공처리하지 않는다.
- 사례별3회,중간 typed 결과를 개별 새파일로 저장한다. 중단된 실행은 살아있는 handle을 확인하고 같은실행을 관찰하며, 완료된run은 재호출하지 않는다. 손상된checkpoint나 설정변경은 조용히덮어쓰지않는다.
- 평가 전 합성테스트로 누락·오분류·반복·부정·검토안·근거오류·부분응답·모드/문서/해시변조·정답미검토를 검증한다. 실제SDK 로컬경로와 전체기존tests/runtime_tests를 통과시킨다.
- 검토자가 독립 전체리뷰1회 수행한다. featurepush와정확한CI를검증한다. 실제모델30회 결과/오류/노출상태를 기록한다. 정답작성/본문노출이후 이 세트로 파이프라인을수정하면 튜닝세트로전환하고 새최종자료가필요하다.

Spring저장·사용자수정량·배포환경 검증은 전체목표에 남는다. 이 평가의완료를제품실사용완료로대체하지않는다.

## 구현 전 확정 계약 (2026-09-30)

- 자료 확보: PUBLIC01/02/03/06/07/08/09/10/11/12, 10개 원본 검증 완료. `corpus.json`은 확보 시점 상태다. `freeze.json`의 content_read=false 역시 고정 당시 상태이며 이후 열람을 부정하지 않는다. 본문은 모두 열람했고, 현재 사전 골드는 207단위/29제외/12모호성 기록이다. API 실행은 0회다.
- PUBLIC02의 원문 대상은 저장소 이름과 달리 Cal.diy다. Cal.com/Cal.diy는 동일 노출 계열로 취급한다. 상용판과 커뮤니티판의 제거 기능을 혼동하지 않도록 부정 사례로 등록했다.
- 골드는 에이전트가 만든 초안이다. `enumerated`도 사람 확인이나 의미적 완전성을 보증하지 않는다. 역할이 불명확한 기술은 억지로 한 필드에 넣지 않고 partial로 표시한다. 짧은 README에 기술이 없다는 사실을 ‘기술을 사용하지 않음’으로 바꾸지 않는다.

### Task 1 형식과 함수

`verify_corpus(cases: list[dict], prior: list[dict], root: Path) -> list[dict]`
- cases 1~10개. 실제 실행기는 정확히10개를 요구한다. 기존 corpus의 정확한 키 집합만 허용한다. id는 PUBLIC-두자리, family는 owner/repo, commit은40자리hex, sha256은64자리hex, source는 해당 family/commit/path의 정확한 GitHub URL, path는 README.md, local_file은 id.md. 파일 경로는 resolve 후 root 내부, 파일은 일반파일/비심볼릭링크, UTF8·100000bytes·100000codepoints·bytes/characters/hash 일치.
- prior는 실제 과거 manifest의 repo/sha256을 사용한다. 대소문자 무시 계열과 원본해시를 중복 검사한다. calcom/cal.com, calcom/cal.diy를 같은 계열로 정규화한다. content_reviewed/seen=false 같은 메타데이터로 노출 검사를 생략하지 않는다. 성공 시 새 메타데이터 사본, 실패 시 내용 없는 ValueError('INVALID_CORPUS').

`validate_gold(document: str, gold: dict) -> dict`
- 문서별 exact keys: case_id, source_sha256, human_reviewed(false), fields, exclusions, ambiguities. source_sha256은 원문 UTF8 해시다.
- fields는 Profile 10필드의 정확한 집합. 필드값은 {assessment, units}; assessment는 enumerated/partial/unspecified. unspecified는 units가 비고, enumerated는 하나 이상. scalar필드는 최대1단위, array필드는 최대30단위.
- unit은 {id:U세자리,kind:present|explicit_absence,spans:[{start,end}]}. ID는 문서 전체 유일, 인덱스는 bool 아닌 int/반열림 코드포인트/원문 내부, 구간 중복 금지. present 구간은 길이1~200. explicit_absence는 배열 필드에만 단독으로 가능하다. 같은 필드의 다른 단위에 같은 구간을 등록할 수 없다.
- exclusions/ambiguities는 각각 {id:X세자리|A세자리,fields:[필드],reason,spans}. reason은 exclusion:negated/tentative/other_product/development_only/community_only/wrong_role; ambiguity:role_not_explicit/development_scope/database_host_only/provider_not_named/integration_or_library/static_asset_or_api/demo_host_only. 필드·ID·구간 중복 금지. 같은 필드·정확한 구간이 정답과 제외 또는 모호성에 동시에 등록되면 골드 오류. 모든 구간 총합 최대10000. 반환은 사본, 오류는 ValueError('INVALID_GOLD').

`score_confirmation(document: str, document_id: str, gold: dict, outcome: dict) -> dict`
- 입력 골드 검증은 항상 먼저 수행한다. document_id==case_id. needs_confirmation은 기존 validate_candidate_confirmation으로 전체 계약·근거를 재검증한다. failed는 정확한 contract/outcome/error 3키와 allowlisted safe code만 허용한다. 나머지는 invalid로 기록한다.
- 반환 exact keys: version='independent-profile-score-v1', status=valid|failed|invalid, error(고정 안전 코드), human_reviewed=false, release_gate_passed=false, evidence_invalid(0|1), questions(0~10), field_states(3상태 개수), fields(10필드), items(안전한 위치 레코드).
- 각 fields 값: assessment, gold, produced, matched, missing, known_wrong, duplicates, unassessed. missing=gold-matched. produced=matched+known_wrong+duplicates+unassessed. failed/invalid는 전 필드 matched/produced=0, missing=gold이며 분모를 유지한다.
- 출력값의 원문 등장을 해당 필드의 검증된 evidence 안에서 **겹치는 등장까지** 전부 수집하고 구간 중복 제거한다. 모든 등장 구간이 동일한 단일 골드 단위에 정확히 대응할 때만 matched. 단일 단위가 이미 매칭됐으면 duplicate. 모든 구간이 해당 필드의 정확한 제외 기록에 대응하면 known_wrong. 다른 필드 정답에만 등록된 경우는 의미 역할 중첩이 가능하므로 unassessed다. 오분류를 known_wrong으로 세려면 해당 필드에 wrong_role 제외 근거를 명시적으로 등록해야 한다. 모호성 기록, 미등록 구간, 정답/제외 혼합, 여러 단위 매칭은 unassessed. 한 출력이 여러 단위를 채우지 못한다.
- 빈 배열도 1개 출력 항목이다. 근거 구간 전체가 명시적 부재 단위에 정확히 대응할 때만 matched. null은 출력0개다. 부재 단위가 없으면 빈 배열은 unassessed다.
- 항목 레코드: field, index, value_sha256(null은 빈 배열만), occurrences(구간), occurrence_overflow(bool), classification=matched|duplicate|known_wrong|unassessed, unit_id(U ID 또는null). 최대128개 서로 다른 등장까지 기록하며 초과는 occurrences=[]/overflow=true/unassessed. 원문·값·인용·예외 내용은 반환하지 않는다.

### Task 2/3 실행 계약

- 새 worker stdin은 document/documentId/solarKey/nvidiaKey/gold exact keys; 키·문서는 메모리에서만 사용한다. 기존 execute_integrated_analysis를 호출하고 Task1 score만 stdout에 JSON 1개로 쓴다. stdout 상한1.5MB, stderr는 부모가 폐기한다. provider예외는 고정코드로 바꿔 실패 score를 만든다. 프로세스 종료·시간초과도 부모가 실패 score로 집계한다.
- 입력 packet/출력 score를 엄격히 검증하며 live명시·키형식·10문서·각골드·소스/코드/골드/evaluator해시가 모두 유효하기 전 외부 호출0회. 기존 production117파일은 수정하지 않는다.
- output 디렉터리에 experiment.json(설정/전체해시), PUBLIC-NN-run-R.started.json, PUBLIC-NN-run-R.json(R=0,1,2)을 배타적 생성한다. started를 먼저 생성하고 최종 결과 후에도 보존한다. 최종파일이 있으면 완전검증 후 skip; started만 있으면 재호출을 금지하고 INCOMPLETE_RUN으로 종료한다. 임의 오래된 시간으로 중단을 추정하지 않는다. 실행 소유 프로세스/세션 handle 관찰로만 종결을 판단한다. 이미 실행된 API가 중복 과금되는 것보다 명시적 중단 복구를 우선한다.
- terminal row는 case_id/run/source_sha256/gold_sha256/freeze_sha256/evaluator_sha256/elapsed_seconds/score exact keys. 오류 텍스트·모델 결과를 추가하지 않는다. 결과와 manifest는 쓰기 후 다시 읽어 형식/해시 검증한다.
- CLI 및 테스트의 정확한 함수 인자는 Task2 brief에서 이 wire와 일치하도록 고정한다. 완료조건은30개의 terminal row다. 중단 표식만 있는 요청은 완료 건으로 세지 않는다.
