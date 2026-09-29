# 호출 진단 검증

- 수집기·CLI 옵션 미구현 실패를 확인한 뒤 구현했다.
- 선택형 호출 메타데이터는 원문·정답·응답 내용을 담지 않는다. 미완료 length 응답의 stage·토큰 수가 보존되고, 알 수 없는 종료 사유는 unknown으로 바뀌며, 수집 유무의 요청이 동일함을 테스트했다.
- 관련 14개 테스트 통과. 전체 831개 실행, 6개 건너뜀, 나머지 통과. diff 공백 검사 통과.
- 실제 CLI에서 --review-diagnostics 단독 실행은 --split-review 필요 오류로 데이터 로드·API 호출 전에 거부됨을 확인했다.
- 독립 리뷰에서 수정이 필요한 코드 결함 없음. 리뷰어는 malformed usage/choice/message, 계약 실패, 잘못된 모델·종료 사유, transport 예외의 합성 7건을 별도 검증하고 안전한 기록을 확인했다. 이 경계 사례 전체를 영구 회귀 테스트로 남기지는 않았다.
- 코드 커밋 e9960a9 push 및 Linux CI 36618473354 성공을 확인했다. 실제 H02 진단 평가는 실패 종료했으며 실사용 품질 개선은 아직 입증되지 않았다.

## 다음 행동

승인된 H02를 source-occurrences/stage-diagnostics/split-review/review-diagnostics로 실행했다. 프로세스 PID 30404, 시작 UTC 2026-09-29T19:20:01.9514001Z. 시작 셸 세션은 34082다. PID와 시작 시간을 함께 대조해 재사용된 PID를 오인하지 않는다.

- 출력: E:/AgentFit/tmp/candidate-review-diagnostics-h02-20260930-v1.json
- 프로세스 기록: E:/AgentFit/tmp/candidate-review-diagnostics-h02-20260930-v1-process.json
- stdout/stderr: 같은 이름의 .stdout.log/.stderr.log. 원문 응답이 아닌 실행 로그이며 Git에 추가하지 않는다.
- 실행은 종료됐고 최종 결과 파일을 확인했다. 시작 셸은 exit 0이지만 평가 JSON은 failed=1이다. 시작 셸의 종료 코드를 모델 성공으로 해석하지 않는다.
- 앞선 분리 검토 평가 세션 47832는 이미 실패 종료했다. 다음에는 새 결과의 review_calls로 candidate_batch/source_coverage, finish_reason, completion_tokens를 확인해 원인을 좁힌다.

## 실측 결과

- H02 총 1,120,223ms, COVERAGE_REVIEW_FAILED / INCOMPLETE_RESPONSE. 최종 Profile 채점 불가.
- 후보 묶음 1: 20개, stop, 입력 7,585토큰·출력 3,125토큰, 151,416ms, 계약 유효.
- 후보 묶음 2: 20개, length, 입력 8,019토큰·출력 8,192토큰, 300,190ms, 계약 미완료. 이번 실패는 출력 토큰 상한 도달로 확인됐다. 전체 원문 누락 검토에는 도달하지 않았다.
- C01/C05/C06 양성 항목은 이번 실행에서 모두 grounded/classified=true다. 최종/검토 이후는 미평가이고 expect_null 3항목도 미평가다.
- 다음 실험은 length로 실패한 후보 묶음만 최대 5개 하위 묶음으로 나누고 전부 검증된 경우에만 계속한다. 재추출 없이 같은 문서·후보·라벨을 사용하며, 작은 묶음의 실패는 그대로 전체 실패다. 원문 누락 검사와 다른 종류의 오류는 재시도하지 않는다.
