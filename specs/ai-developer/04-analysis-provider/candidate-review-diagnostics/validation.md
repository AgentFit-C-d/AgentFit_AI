# 호출 진단 검증

- 수집기·CLI 옵션 미구현 실패를 확인한 뒤 구현했다.
- 선택형 호출 메타데이터는 원문·정답·응답 내용을 담지 않는다. 미완료 length 응답의 stage·토큰 수가 보존되고, 알 수 없는 종료 사유는 unknown으로 바뀌며, 수집 유무의 요청이 동일함을 테스트했다.
- 관련 14개 테스트 통과. 전체 831개 실행, 6개 건너뜀, 나머지 통과. diff 공백 검사 통과.
- 실제 CLI에서 --review-diagnostics 단독 실행은 --split-review 필요 오류로 데이터 로드·API 호출 전에 거부됨을 확인했다.
- 독립 리뷰에서 수정이 필요한 코드 결함 없음. 리뷰어는 malformed usage/choice/message, 계약 실패, 잘못된 모델·종료 사유, transport 예외의 합성 7건을 별도 검증하고 안전한 기록을 확인했다. 이 경계 사례 전체를 영구 회귀 테스트로 남기지는 않았다.
- 코드 커밋 e9960a9 push 및 Linux CI 36618473354 성공을 확인했다. 실제 H02 진단 평가는 실행 중이며 실사용 품질 개선은 아직 입증되지 않았다.

## 다음 행동

승인된 H02를 source-occurrences/stage-diagnostics/split-review/review-diagnostics로 실행했다. 프로세스 PID 30404, 시작 UTC 2026-09-29T19:20:01.9514001Z. 시작 셸 세션은 34082다. PID와 시작 시간을 함께 대조해 재사용된 PID를 오인하지 않는다.

- 출력: E:/AgentFit/tmp/candidate-review-diagnostics-h02-20260930-v1.json
- 프로세스 기록: E:/AgentFit/tmp/candidate-review-diagnostics-h02-20260930-v1-process.json
- stdout/stderr: 같은 이름의 .stdout.log/.stderr.log. 원문 응답이 아닌 실행 로그이며 Git에 추가하지 않는다.
- 마지막 확인에서 PID가 실행 중이고 결과 파일은 없었다. 이 기록만으로 현재 활성 여부를 판단하지 말고 프로세스/결과를 확인한다. 종료 전 중복 실행하지 않는다.
- 앞선 분리 검토 평가 세션 47832는 이미 실패 종료했다. 다음에는 새 결과의 review_calls로 candidate_batch/source_coverage, finish_reason, completion_tokens를 확인해 원인을 좁힌다.
