# 후보 분석 보완의 전체 경로 연결

## 목적과 현재 근거

실사용 가능한 AgentFit AI가 목표다. 사용자는 이번 목표에서 설계·계획·구현에 별도 승인을 요구하지 않았고 직접 SDD와 기능별feature push를 선택했다. 직전 관계 합성 회귀는48/48이었지만 올바른후보·분류가주어진한관계의평가였다. 현재 `analyze_candidate_first`는 동작후보 보강·NVIDIA 사유검토·대표구성/복구를 호출하지 않는다. `finalize_candidate_analysis`에만 feature_curation 입력이 있다. 최근 보완을 한 경로에서 실행·검증할 수 있도록 선택형 전체 분석 함수를 만든다.

## 접근 선택

1. 임시 재생 스크립트를 계속 조합하면 원래 추출·분류를 건너뛴 점수를 전체 품질로 오인하기 쉽다.
2. 기본 분석 함수에 제공자별 옵션을 계속 추가하면 기존 Solar 서비스 경로의 설정과 혼합된다.
3. **선택:** 기존 helper를 조합하는 전용 내부 함수. 후보를 원문 위치로 합친 뒤 같은 분류기로 판단하고 검토·대표복구를 연결한다. 기본HTTP/공개Profile은변경하지않고전체품질검증후서비스연결을판단한다.

두 출처를 각각 분류한 뒤 합치던 기존 임시 실험과 달리, 먼저 원문 위치를 합치고 한번 분류한다. 같은 위치에 서로 다른 분류가 생기는 구조를 피한다. 이 변화의 의미 품질은 새 실제 실행으로 검증하며 과거 snapshot 점수를 그대로 재사용하지 않는다.

## 계약과 흐름

새 `candidate_analysis_pipeline.analyze_integrated_candidates(document, document_id, solar_key, nvidia_key, *, review_model='z-ai/glm-5.3', feature_model=MODEL, extractor=None, solar_transport=None, nvidia_transport=None, observer=None, call_trace=None, review_calls=None, max_calls=64) -> dict`.

1. 입력·설정 전부 사전검증: 원문비공백/최대100,000codepoints,document_id비공백문자열,두키비공백·원문/id에키없음,모델기존NVIDIA3종,callback/collector형식,max_calls정수1~64(bool금지). 잘못된값은외부호출0회ValueError.
2. 기존 Solar LangExtract 일반후보 추출8192토큰→모든정확발생위치확정.
3. feature_model(기본DeepSeek)의 동작후보1회추출. 원문위치와반려사유를기존helper로검증.
4. 두 frozen 집합을원문(start,end)로중복제거·정렬하고C000부터안정ID재부여. 모든반려사유보존.240후보초과시절단없이실패.
5. 합친전체후보를Solar의 `classify_profile_candidates(...field_semantics='explicit-v1')`로30개씩분류. 추출시가정한필드·상태를분류정답으로물려주지않는다.
6. review_model(기본GLM)의 기존분할검토,explicit-v1,reasoned_review=True,adaptive_review=False.20개확정후보씩검토후원문커버리지1회.두단계모두유효해야다음으로진행.
7. 검토반려ID를제외한safe_labels만 `curate_reviewed_features`에전달한다.30개초과일때만대표선택·쌍별검토·한번복구(기존최대4호출).검토반려후보를복구에서되살리지않는다.
8. 기존finalizer에원래labels/review/검증된curation을전달한다.다른9필드·근거·반려/누락/미포함의확인필요사유를유지한다.대표자기근거·30개상한등기존Profile검증을재사용한다.

공통순수함수 `apply_candidate_review(frozen, labels, review) -> list[dict]`를기존finalizer에서추출한다.전체검토계약을먼저검증하고반려ID상태를irrelevant로바꾼복사본을반환한다.통합함수와finalizer가같은검증을사용한다.

## 오류·호출·관측

- provider별전송wrapper가모든실제Solar/NVIDIA요청을같은max_calls예산으로센다.상한초과시다음전송전중단한다.자동retry/fallback은추가하지않는다.기존요청timeout600초·8192출력과LangExtract4000자청크를유지한다.64는연구경로의강제호출상한이며전체시간을보장하지않는다.
- 주입extractor는단위테스트/기존인터페이스용이다.기본extractor에만wrapper를연결해모든실호출을센다.임의주입callback이밖에서만드는네트워크까지계측한다고주장하지않는다.
- 실행오류는고정단계 EXTRACTION_FAILED,GROUNDING_FAILED,OPERATION_EXTRACTION_FAILED,MERGE_FAILED,CLASSIFICATION_FAILED,COVERAGE_REVIEW_FAILED,FEATURE_CURATION_FAILED,PROJECTION_FAILED,DIAGNOSTIC_FAILED의CandidatePipelineError로전달한다.키/원문/공급자예외본문은오류문자열에없다.호출한도는고정detail CALL_BUDGET_EXCEEDED로남긴다.
- call_trace에는stage/provider/requested_model/call_index/elapsed_ms/response_bytes/transport_completed만추가한다.전송완료와의미계약검증성공을구분한다.기존review_calls는분할검토의안전한진단을재사용한다.
- observer는합친grounded→classified→reviewed→projected를기존형식의복사본으로받는다.콜백오류는분석중단으로전달한다.관측내용을함수스스로저장/출력하지않는다.

## 검증과 실사용 관문

실제helper+제공자transport fake로일반/동작후보합치기→분류→검토→대표구성/복구→최종Profile을한테스트에서통과시킨다.중복위치ID,다른9필드유지,반려후보제외,누락·미포함확인상태유지,같은partition재표본추출금지,키경로분리,호출상한·단계실패·observer실패를검증한다.기존기본분석기와HTTP회귀를통과해야한다.

최초실측은이미API전송승인된H02/MyPort1건을새추출부터실행한다.기존6개검사는부분검사로보고단일문서정확도로확대하지않는다.필요하면외부전송을fake한통합연결검증과실제모델품질을분리한다.개인문서/모델응답을세션출력/Git저장하지않고키도출력하지않는다.발췌열람승인대기는유지하며이실측으로원문감사를대체하지않는다.

제품코드/manifest/source/redacted해시고정,신규로컬보고서,실행중같은핸들관찰,진행/종료명시,실패분모보존,독립코드리뷰1회·전체회귀·feature push·정확CI를요구한다.합성관계세트나단일문서6항목통과로전체목표를완료하지않는다.실제Spring확인/저장,다문서독립평가,누락/오분류·대표품질은계속남는다.

## 자체검토

모델역할·키경로·라벨시점·누락게이트·64호출범위가명확하다.반려후보제외를finalizer와공유한다.원문열람차단을우회하지않으며기존HTTP기본설정을건드리지않는다.사용자자율승인범위에서계획·직접구현으로진행한다.
