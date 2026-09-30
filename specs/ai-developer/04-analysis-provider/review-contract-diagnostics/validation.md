# 검토 계약 진단 검증

## 로컬 검증

- 기준 e544650: 전체989건, 983통과·플랫폼6제외, 19.449초/exit0.
- 신규7개 테스트 RED: 진단 항목 누락으로49개 실패, 파싱·거절 및 중단에 관한 기존 assertion은 통과.
- 구현 후 신규7/7 통과, 0.014초/exit0. GLM/Solar, 사유 검토 유무, 목록과 사유의 다중 위반, 중첩 객체/목록, 잘못된 응답 문자열 비노출, 기존 collector 보존을 포함한다.
- 전체996건 중990통과·기존6제외, 19.552초/exit0. 실제 API 호출0.
- payload와 boolean validator를 변경하지 않았다. 잘못된 응답은 기존 ValueError/INVALID_REVIEW_CONTRACT로 거절하며, 통합5번째 호출의 의미 실패는 재시도나 투영 없이 COVERAGE_REVIEW_FAILED로 종료한다.

## 남은 증거

- 구현06d1e04242f260abdfa40724f8ffd242ee14bf33. Task1 최종 전체996건/990통과6제외,19.616초/exit0.
- 독립 리뷰 Critical0/Important0/Minor0. 리뷰어가 신규7개를 직접 재실행해 통과했고 기존 파서·검증·중단 경로를 확인했다. 전체 suite와 모델 품질은 부모의 별도 검증이다.
- feature/review-contract-diagnostics push 성공. 정확한 구현 커밋의 [Linux CI36674103301](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36674103301) completed/success. 의존성 호환·실제LinuxPDF메모리·전체suite 단계 통과.
- 새H02 드라이버 합성 회귀3/3, 사전검사 API0/7665자/부분정답6개, 동결 해시 확인. 승인된 실제 평가 session56367/PID36160 시작. 드라이버·보고서: E:/AgentFit/tmp/review-contract-h02-20260930-v1.py 및 .json. 감사: E:/AgentFit/tmp/audit-review-contract-h02-20260930-v1.py.
- 실제 결과 대기. Solar2회 반환 후 NVIDIA3번째 호출 진행을 session56367에서 확인했다. 이 변경은 관측 기능이며 과거 모델 실패의 원인이나 의미 정확도 개선을 아직 입증하지 않는다.

## H02 실제 평가 종료 — 2026-09-30

- 같은 session56367/PID36160은 exit1로 종료했다. 총17호출, 2,730,631ms(약45.5분). 제품·드라이버·문서·manifest 해시 및 집계 분모 등 감사18항목이 모두 통과했다. 제품 코드 변경 없음.
- 원문 후보204개, 제외7개. 분류는 confirmed112/tentative21/irrelevant48/negated23이었다. 이는 최종 정답 수가 아니다.
- 후보 검토1~5묶음(각20개)은 응답 계약을 통과했다. 6번째 묶음12개의 호출16이 PROVIDER_UNAVAILABLE로 실패했고, 허용된 재시도 호출17도 동일하게 실패했다. 각 시도는 약302.5초였다. retry_attempts1/transport_recoveries0/failed_transport_attempts2.
- 최종 COVERAGE_REVIEW_FAILED/PROVIDER_UNAVAILABLE, complete0/needs_confirmation0/failed1. 전체 원문 누락 검사·대표 기능 구성·최종 Profile까지 도달하지 않았다. 부분 정답6개는 모두 미평가(checked0/suggestion_checked0)이며 정확도0/6으로 해석하지 않는다.
- 6개 review_calls의 contract_issue는 모두 null이다. 앞5개는 계약 통과, 마지막은 파서·계약 검사 전 전송 실패다. 과거 계약 오류가 해결됐다고 결론 내리지 않는다. 이번 관측 변경은 프롬프트나 수락 조건을 바꾸지 않았다.
- 별도 합성 형식 비교2호출과 계정 사용 시간이 겹쳤으므로 이전 실행과 순수 지연 비교를 하지 않는다. 이번 문서는 튜닝에 노출됐고 부분정답만 있어 독립 품질 검증을 대체하지 않는다.
- 진행 안내에서 호출16 반환 후 전체 누락 검사로 진입했다고 말한 것은 잘못이었다. 실제 호출17은 6번째 후보 묶음 재시도임을 최종 trace로 확인하고 정정했다. 이후 단계 진입은 반환 이벤트만으로 판정하지 않고 시도 번호·검토 stage·오류를 함께 확인한다.
