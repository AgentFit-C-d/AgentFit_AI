# 상태 (최신: 문맥 규칙 반영·로컬 검증·push·Linux CI 완료)

## 재개 지점

- 전체 목표는 실사용 가능한 AgentFit AI이며 아직 미완료다. 이번 기능의 세 작업은 구현·검증됐으며 마지막 문서 커밋 뒤 Task3 task-done으로 기록한다.
- 브랜치: `feature/candidate-feature-relations`, 작업 폴더: `E:/AgentFit/tmp/worktrees/source-name-expressions`.
- v2 실험 종료: 셸92390/PID26072 exit0, 33,153ms, 코드 불변. 지정 판단34/36, 오포함0, 유효 관계 오거절2(C134/C110). 모호2개는 제외. 두 분할 모두 확인 필요이며 다른9필드/labels 불변이다.
- 실험과 같은 일반 문맥 규칙을 helper에 추가했다. 두 고정 분할(6쌍/32쌍)에서 실험 요청과 제품 요청 전체 일치, 외부 호출0, 요청 저장0을 확인했다. 임시 복사본 해시 차이는 CRLF/LF뿐이었고 정규화 후 평가 원본 해시와 일치했다.
- 수정 후 전체 테스트:907개,901통과/6건너뜀,실패0,exit0,14.790초. `E:/AgentFit/tmp/candidate-feature-relations-context-full-tests.log`. 셸85342 종료 확인. 실행 중인 API/테스트 프로세스 없음.
- 독립 리뷰는9b583c4..58c8e52에 대해 완료됐고 결함0이다. 이후 문맥 지침 추가는 실제 비교·요청 일치·전체 회귀로 별도 검증했다. 재리뷰하지 않는다.
- 구현 `a25965276ee48eb7f28a99694e84698c47261720` push 완료, 정확한 Linux CI `36650027778` completed/success. 이후 변경은 결과 문서뿐이다. 자동 승인 검토가 한 차례 기록 갱신을 다른 worktree 수정으로 판단해 차단했으나, 절대 경로·브랜치·링크 아님을 확인한 재검토 후 현재 작업 폴더의 두 기록만 갱신했다. 보호 경로는 수정하지 않았다.
- 다음 품질 관문: 잘못된 대표 그룹 재구성, 유효 관계 오거절/선행 누락 보완, 다문서 반복, HTTP/Spring 통합. 이번 사용자 요청에는 현재 진행상황과 제한을 보고한다.
- 단일 튜닝 문서의34/36을 전체 정확도나 진행률로 사용하지 않는다. 기본서비스 승격/배포 없음.

## 이전 이력

- 전체목표: 실사용가능AgentFit AI,active/미완료. 자율SDD·직접구현·기능별featurepush승인됨.
- 브랜치feature/candidate-feature-relations,base9b583c4. E:/AgentFit/tmp/worktrees/source-name-expressions재사용. 시작Gitclean,선행실험모두terminal.
- 이전goalturn:progress. 정규화수정0e51a48·평가29대표/6미포함·893pass6skip·정확CI성공·9b583c4까지push. 역순진단에서9대표/41미포함/자기대표9개모순확인.
- 결정: 자기포함/미대표는서버계산,서로다른후보의정확한pair만covered/not_covered/uncertain으로평가. 두고정분할의6/32관계로검토효과분리. 기본서비스/공개Profile불변.
- 현재: 구현58c8e52212c47b188c800901e46eeb43d3714e17 push. Task1/2 task-done 완료. 통합22/22,전체907개901pass/6skip/exit0,최종 task-done14.887초. 제품코드 동결. 독립리뷰 candidate_feature_relations_review가9b583c4..58c8e52를 읽기전용 검토 중.
- Task3 v1 종료: 셸47679/PID7656 exit0,finished/code_unchanged=true,40,266ms. 지정29/36(원래6/6,역순23/30),모호2개는covered. 보류0,오포함7개(C013/C056/C067/C069/C111/C131/C160). 자기 모순9→0이나 의미 안전성 충족 아님. 다른9필드/labels 불변,확인필요 유지.
- 독립 리뷰 종료:9b583c4..58c8e52에서 결함 없음,자체22/22·diff --check PASS. 정확한 구현CI36648154630 success. 실제 모델 품질·다문서·공급자최대입력·서비스연동은 리뷰 범위 밖이며 부모가 구분 기록한다.
- 후속 한정 진단: context-probe.md. 동일 두 분할과 사전판정을 유지하고 system message에 대표 value의 기능 범위를 주변 문맥의 다른 동작으로 확장하지 않는 일반 규칙만 추가. 제품코드동결,최대2호출. E:/AgentFit/tmp/run-feature-relations-context-h02.py,preflight PASS,셸92390/PID26072 시작확인. 새결과 candidate-feature-relations-h02-20260930-v2.json. 같은핸들로관찰하며기존v1은재시작하지않는다.
- 검증제한: H02튜닝문서,사전36판정은개발자한정감사이며전체정확도아님.2모호관계별도. 상류의잘못된후보/누락·잘못된대표선정·다문서반복·HTTP/Spring연동은전체목표에남는다.
- 보호: 다른worktree의사용자소유work/harness/service-readiness는수정하지않는다. 원문/키/응답전문은저장하지않는다.
