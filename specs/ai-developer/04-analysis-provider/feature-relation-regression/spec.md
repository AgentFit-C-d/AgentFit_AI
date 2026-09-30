# 기능 포함 관계의 고정 합성 회귀 평가

## 목적과 범위

실사용 품질의 한 관문으로 대표 기능의 포함 관계 판단을 반복 측정한다. 현재 H02 그룹 복구의 새 의미 감사는 발췌 열람 승인 대기다. 그 원문이나 파생 문구를 사용하지 않고 독립적으로 작성한 허구 사례를 평가한다. 사용자는 반복·부정·검토안 사례를 포함한 자동 평가와 자율 SDD 구현을 요청했다.

코드의 canned 응답 테스트는 서버 검증을 증명하지만 실제 모델의 의미 판단을 측정하지 않는다. 같은 개인 문서 반복은 미해결 감사에 의존한다. 따라서 고정된 합성 사례·정답을 응답 전에 커밋하고 현재 제품 `review_feature_relations`를 호출하는 회귀 CLI를 추가한다. 그룹 생성·후보 추출·분류·HTTP는 이번 측정 범위가 아니다. 실제 문서 감사와 서비스 품질 기준은 별도로 유지한다.

## 코퍼스

- `cases.json`에 독립 허구 사례12개를 작성한다. 실문서의 제품명·문구·정답·후보ID를 복사하지 않는다. 모든 내용은 테스트용 창작 문장이다.
- 명확한 포함5개: 명시 별칭, 같은 기능의 반복 발생, 명시된 복합 동작의 하위 동작, 같은 정책의 다른 표현, 명시적 등급 부여와 라벨링 별칭.
- 명확한 미포함7개: 조건절과 후속 동작, 같은 흐름의 다른 작업, 다른 대상, 부정된 통합, 검토 중인 통합, 같은 문구의 다른 범위, 문서에 삽입된 응답 지시.
- 각 사례는 `id`(FR두자리),`document`,`representative`/`member`(quote와0기반occurrence),`distractors`(quote/occurrence/status),`expected`(covered/not_covered)만 가진다. 후보 C000/C001은 확정 기능, 추가 후보는 명시된 negated/tentative다. 이 분류를 정답으로 공급하므로 분류 정확도를 측정했다고 말하지 않는다.
- 정확 인용의 모든 겹침 허용 발생 위치를 찾고 지정 occurrence로 위치를 고정한다. 인용/순번 오류,동일 위치 중복,사례ID 중복,추가키/자료형/상한 오류는 전송 전에 거절한다. 원문 최대100,000자,최대24사례,각최대240후보다. 대표값 최대200자와2후보1관계의 기존 partition도 검증한다.
- 입력순서 original/reversed는 frozen 후보 배열만 뒤집고 원문·ID·근거 위치·분류·관계·정답은 유지한다. 각입력2회가 기본이다. 정답과distractor라벨 등 평가 메타데이터는 모델 요청에 새로 추가하지 않는다.

## 실행 및 집계

- `agentfit_ai.feature_relation_evaluation`에 `prepare_case(case)`, `load_cases(path,expected_sha256)`, `evaluate_cases(cases,key,*,model=MODEL,repeats=2,transport=None,checkpoint=None)`를 구현한다. prepare_case는 원문/frozen/labels/partition과평가ID/expected를 반환한다. evaluate_cases는 corpus를사전검증한뒤 실제helper를호출한다.
- 기존 NVIDIA3모델 허용목록과keyloader를 재사용한다. 기본DeepSeek V4.1 Flash. 모델설정은기존adapter그대로,timeout600초/출력8192/호출당1관계/재시도0이다. repeats는정수1~3,최대24×2×3=144호출이다. 최초실측은12×2×2=48호출이다.
- 실제coverage enum은 검증된 단일관계 결과와 안전한 trace의 covered/not_covered/uncertain 개수로 복원한다. 모델응답전문을별도로저장하지않는다. 구조/전송실패는failed로기록하고계획분모에서빼지않는다.
- 각행은case_id/order/repeat/expected/actual/elapsed_ms/안전오류/허용provider메타데이터와개수만기록한다. 원문·인용·키·응답전문·추론은보고서에없다. 오류문자열을그대로기록하지않는다.
- 집계는planned/completed/matched/false_covered/false_uncovered/uncertain/failed와순서·반복일관성을분리한다. uncertain은정답으로세지않는다. 순서일관성은같은case/회차의유효2응답이같을때만성공,반복일관성은같은case/order의모든반복이유효하고같을때만성공이다. repeats1에서는반복일관성평가분모0이다. failed끼리같아도일관성성공이아니다.
- 회귀통과는계획행수모두완료하고모두지정정답일때뿐이다. 이통과는합성관계회귀일뿐서비스정확도·진행률·출시승인을뜻하지않는다.
- CLI는`--preflight` 또는`--live`,고정코퍼스SHA256,새output경로를요구한다. preflight는키를읽거나API호출하지않는다. live는키·입력검증후새파일을배타생성해기존결과덮어쓰기를거절한다. 초기와각행후안전한진행기록을저장한다. checkpoint실패는호출을계속하지않고전달한다.
- 코퍼스 해시는CRLF→LF정규화바이트로검증한다. 코드해시는실행전후확인하고종료시code_unchanged를기록한다. 소스가바뀌면실험은유효한완료로처리하지않는다.

## 수용 기준과 후속

중복/오류근거/불필요후보배제,정답미전송,두순서·반복호출수,오포함/오거절/불확실/실패분모,순서일관성,checkpoint실패전파,키/원문비노출,기존파일보호를실제consumer동작테스트로검증한다. 관련/전체회귀·독립코드리뷰1회·기능push·정확CI를확인한다.

실호출결과는지정48행을빠짐없이보고하고모델통과와실패를관측대로기록한다. 결과를본뒤이코퍼스를독립holdout이라부르지않는다. 오류가나오면유형별재현근거로활용하되개인문서감사를대체하지않는다. 기존H02발췌승인은계속대기중이며우회열람하지않는다.
