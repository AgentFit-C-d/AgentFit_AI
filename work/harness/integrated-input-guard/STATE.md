# 통합 입력 검사 상태

## 목표와 작업 공간

- 전체 실사용 목표 active. 자율 SDD·직접 구현·feature push 승인 유지. 실제 API 실행·리뷰 대기 없음.
- 현재 후속 작업용 checkout E:/AgentFit/tmp/worktrees/integrated-input-guard, branch feature/integrated-input-guard. base7d6f1b7, spec/plan e7a113e, 제품cc4e69c8f95e4af6e290e18fd6422cb5f1fa28e6.
- 앱 worktree 생성은 Git 소유권 오류로 불가해 확인된 Git 제외 경로에 명령별 safe.directory로 생성했다. 전역 설정과 다른 checkout은 변경하지 않았다. 이 checkout은 다음 기능에서도 재사용한다.

## 완료 근거

- 기존 민감값 검사를 문서·ID의 첫 추출 전에 적용했다. 새 regex/모델/공개API 변경 없음.
- RED: 신규5테스트/16subtest 실패. GREEN:5/5, 전체989건/983pass6skip. Task1 최종19.464초/exit0.
- 독립 리뷰 /root/integrated_input_guard_review 완료: Critical0/Important0/Minor1. reviewer도5+20테스트 통과. Minor는 ValueError 하위타입을 구분하지 않는 기존 계약 assertion이며 현재 제품 회귀는 없다. 보류 기록 유지.
- 구현 feature push 및 정확한cc4e69c Linux CI36671877562 success. 의존성 호환·실제LinuxPDF메모리·전체suite 통과. 최종문서 commit/push 및 Task2 diffcheck 후 종료.
- 재시도 실험 최종문서576e32c를75f0999로 가져왔다. 제품 변경 없이 최신 근거를 후속 이력에 유지한다.

## 실제 모델 평가와 다음 행동

- 별도 source-name-expressions의 H02 session15571/PID26560은 terminalexit1. 15호출/약24분/전송실패0/재시도0. GLM 후보20개5번째 검토 INVALID_REVIEW_CONTRACT(stop/920bytes). 최종6검사는모두미평가. 재시작 금지.
- 다음 기능은 검토 계약 오류의 안전 세부 진단. 기존 한 코드로는 checked-ID 순서/집합, wrong-ID 집합, 반려 사유 연결 중 어디가 틀렸는지 판별할 수 없다. 원문·값·모델본문을 노출하지 않는 고정 코드로 나눈 뒤 원인에 맞춰 개선한다.
- 후보/질문 어댑터·긴요청종료·LangExtract설치·Spring저장·실패응답7일만료·독립문서품질은 미완료. 상세 조사: work/harness/nvidia-transient-retry/service-integration-notes.md.
- 개인정보 발췌 표시 및 Spring 저장소 위치 질문은 답변 대기. 승인된 API평가와 발췌 표시는 다르며 키·원문·파생문구는 출력하지 않는다.
