# 전체 후보 분석 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 승인된 직접 순차 구현, 작업별 RED→GREEN, 최종 독립 리뷰1회.

**Goal:** 일반/동작후보 생성부터대표복구·Profile변환까지한선택형함수로실행하고실문서새추출로검증한다.
**Architecture:** 두추출→원문위치합치기→단일Solar분류→NVIDIA사유검토→안전라벨→DeepSeek대표복구→기존finalizer.전송wrapper로양provider의호출상한·안전trace를공유한다.
**Tech Stack:** Python/unittest/기존LangExtract·Solar/NVIDIA어댑터,새의존성없음.
**Spec:** specs/ai-developer/04-analysis-provider/integrated-candidate-analysis/spec.md

## Global Constraints

- branch feature/integrated-candidate-analysis,baseb35fc63,source-name-expressions 재사용. 사용자자율설계/구현/push승인,기본HTTP·공개Profile불변.
- 원문100,000codepoints/최대240후보/대표30개,defaultmax_calls64(정수1~64),요청600초/8192토큰,자동retry/fallback없음.
- Solar일반추출/분류,GLM사유검토,DeepSeek동작추출/대표복구기본. NVIDIA모델은기존3종만설정가능. explicit-v1사용.
- H02는API전송승인만활용한다.원문발췌출력승인은대기중.원문/후보값/키/모델응답전문출력·Git저장금지.

## Review Focus

- 추출기두개가같은위치를반대로나열: Task1 위치정렬·중복제거·다른위치보존테스트.
- 검토반려후보가대표구성에서부활: Task2 실제helper통합에서반려ID요청제외·확인상태유지.
- Solar/NVIDIA키교차전송또는한쪽호출예산누락: Task2 실제전송fake에키·모델·누적상한검증.
- observer가상태를변조/예외발생: Task2 입력복사본및DIAGNOSTIC_FAILED·추가호출중단.
- 부분실패를성공으로가리거나null기능을성공으로보고: Task2 실패단계/coverage/미포함/반려게이트,Task3실행실패분모유지.

### Task 1: 공유 검토 라벨 검증과 원문 후보 합치기

**Files:** Modify ai_service/agentfit_ai/candidate_first_profile.py; Create ai_service/agentfit_ai/candidate_analysis_pipeline.py,ai_service/tests/test_candidate_analysis_pipeline.py.
**Interfaces:** apply_candidate_review(frozen,labels,review)->list[dict]는완전검토계약검증후반려ID만irrelevant인복사라벨반환. _merge_occurrences(document,*sets)->frozen은기존_validate_frozen후위치합집합/정렬/C000재키/반려재인덱스/240초과거절.

- [x] **Step1 RED:** 중복위치는하나,같은문구다른위치는둘,입력불변/반려보존/잘못된위치/240초과거절. 검토누락·중복·외래ID거절,반려만irrelevant,결과변조가원래labels를바꾸지않음. `python -m unittest discover -s tests -p test_candidate_analysis_pipeline.py -v` Expected:새함수없어FAIL.
- [x] **Step2 implement:** 기존finalizer의검토검증을순수함수로추출해재사용,기존동작보존. 새모듈에원문위치merge만구현.
- [x] **Step3 GREEN/commit:** Step1새테스트PASS,기존candidate_first_profile/feature테스트와전체unittestPASS. task-done은새파일테스트.

### Task 2: 전체 흐름·호출 상한·진단 연결

**Files:** Modify candidate_analysis_pipeline.py,tests/test_candidate_analysis_pipeline.py; Create specs/.../integrated-candidate-analysis/README.md.
**Interfaces:** analyze_integrated_candidates(document,document_id,solar_key,nvidia_key,*,review_model='z-ai/glm-5.3',feature_model=MODEL,extractor=None,solar_transport=None,nvidia_transport=None,observer=None,call_trace=None,review_calls=None,max_calls=64)->기존finalizer결과dict. Task1두함수를사용.

- [x] **Step1 RED:** 실제helper+transport fake로두후보합치기/한번분류/사유검토/31기능대표선택·거절관계복구/최종Profile연결. 대표기능2개·다른9필드유지,반려1개와missingFields확인상태보존. 모델별키·명시적분류정책·추가후보의정확ID전달검증. 30개이하추가curation호출0. 잘못된설정0전송,공급자실패단계,예산초과시추가전송0/detail상수,observer변조안전·실패중단,defaultLangExtract어댑터에계측transport주입. Expected:통합함수부재FAIL.
- [x] **Step2 implement:** 사전검증→단계runner→provider별countedtransport→기존helper직렬조합. 예산flag를전송전세워기존파서/라이브러리가오류를바꿔도단계runner가CALL_BUDGET_EXCEEDED로중단. private예외문구는기록하지않음. 기본추출함수만LangExtract에wrappedSolartransport전달.
- [x] **Step3 GREEN/commit:** 새테스트/관련/전체suite PASS. 호출예산/모델역할/반려게이트·예외범위를README에기록. task-done전체suite.

### Task 3: 실제 H02 전체 실행·리뷰·push

**Files:** Create specs/.../integrated-candidate-analysis/validation.md; Modify work/harness/integrated-candidate-analysis/STATE.md. 임시driver/report는E:/AgentFit/tmp의신규경로.
**Interfaces:** 기존prepare_cases/select_cases/evaluate_cases로승인H02만준비하고새runner를호출한다. 키/원문은메모리에만,stdout/stderr외부라이브러리출력도원문노출하지않게메모리캡처. safeprogress는ID/단계/호출수만허용.

- [x] **Step1 preflight/live:** 실제코드/manifest/source/redacted해시고정. preflight는키조회/전송0. 새결과경로에안전한원자적checkpoint.정확한프로세스핸들/PID관찰,최대64실호출,기존6검사는부분검사. 종료전코드변경·재시작없음. Expected:유효전체Profile또는명시실패/확인상태를보고,미확인을자동성공으로세지않음.
- [x] **Step2 review/fix:** 전체변경독립리뷰1회,치명/중요발견은한번의RED→GREEN수정및전체회귀. Minor는기록,재리뷰없음. 모델의의미감사·Spring연동검증을코드리뷰로대체하지않음.
- [x] **Step3 publish:** feature push/정확구현CI확인,실측지표·제한·다음관문기록. task-done은최종문서만남은상태의base..HEAD diff --check. 전체목표active유지.

## 자체검토

Task1의순수라벨검증을Task2의curation과기존finalizer가동일하게쓴다. 미분류원문후보를합친뒤단일분류하기때문에과거snapshot의labels를유입하지않는다. Task3의6검사와현재48합성관계점수는합산하지않는다. 사용자자율승인에따라직접구현으로진행한다.
