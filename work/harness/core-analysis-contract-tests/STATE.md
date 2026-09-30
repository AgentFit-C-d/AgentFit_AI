# 핵심 분석 흐름 mock·계약 테스트 상태

## 목표·권한·제약

- 전체목표는 입력→분석→사용자 확인·수정→Spring 저장의 실사용 완결성이다. 사용자 승인으로 현재API기반 mock·계약 테스트를 구현한다. Spring 저장소는 현재 제공불가이므로 실제 연동·PostgreSQL·브라우저·운영삭제 검증은 미검증 유지.
- NVIDIA현재계정추가요금0이확인된엔드포인트만호출가능하며현재확인안됨. 무료한도소진/미확인시중단,유료전환/충전/대체금지. Solar별도유료승인없음. 이번기능외부모델0회/0원. 개인문서전송·배포별도승인.
- 기존평가보존: feature/independent-profile-evaluation의23c3235에중단기록push. 모델기준선da49dfb/고정207골드.1/30완료ANALYSIS_FAILURE247.598초, 두번째started-only보존.89953 exit1/runnerworker0확인. 자동재호출없음.

## 작업 상태

- 기존isolated E:/AgentFit/tmp/worktrees/analysis-runtime 재사용. feature/core-analysis-contract-tests, base23c3235. spec6b7ba5c/planb02e319. 직접순차구현.
- Task1 startedBASEb02e31935e860e8a488b5cffa2266bc56f8ec048. 실제공개OpenAPI검증기+메모리저장소구현,9개RED(missingmodule)→GREEN0.024초. precommit전체1117개/5skip45.863초,runtime11/11 40.480초,contract9/9 0.023초,exit0. pipcheck충돌0,frozen117/evaluator6·10문서207골드해시불변. 최종task-done기록은다음확인.
- 확인: 수동저장/재조회,동일값DOCUMENT근거유지/수정USER/미정UNKNOWN,[]구분,초안/확인별도,낡은버전409/다른프로젝트404,동시저장정확히1성공,저장실패불변,반환객체변형격리,미합의draftReview공개필드거절.
- 신규선택의존성jsonschema[format-nongpl]4.26.0을프로젝트.venv에만설치. productionrequirements/agentfit_ai/evaluator코드미변경. 공개OpenAPI파일읽기전용.
- SDD: .superpowers/sdd/plan-core-analysis-contract-tests/progress.md, task-1-brief.md; taskcontrol .superpowers/core-task-control.ps1. verify.py는각suite180초상한으로tests/runtime_tests/contract_tests를실행하고tail만출력한다.

## 다음 작업·검증 한계

- 최신: Task2 d4a77c1 push/최종gate완료. Task3 실패진단/민감값/실제TCP/응답유실 및 인계 문서·CI job구현. precommit전체1117/5skip58.396초,runtime11/11 51.051초,contract34/34 9.252초,exit0,pipcheck충돌0. 전체 최종리뷰와 정확한CI는 아직 남음.
- Task3의 TCP 끊김은 실제 RED→GREEN. 실패시점+7일만료·삭제후쓰기차단, 실제저장뒤응답유실 복구 검증. 공개v2질문 미구현과 실제Spring미검증은 Docs/api/core-analysis-mock-handoff.md 및 analysis-confirmation-v2.draft.md에 명시.

- Task1 완료797b113/push/CI36724997363 성공. Task2 HTTP7+경쟁7+store9=23개 통과. 입력전 admission·삭제중 physicalslot·기한정리·근거끝범위를 RED→GREEN으로 보완했다. 전체1117/5skip44.106초,runtime11/11 38.434초,contract23/23 2.876초,exit0. Task2커밋/최종gate를 진행한다.
- 실제 모델0회, 실제 Spring0회. Task3 합성실패진단7일·로그·localhost TCP·인계·최종리뷰가 남았다.

- Task1전체gate→commit/task-done. Task2 mockHTTP/AI경계/실패·timeout·중복·삭제경쟁. Task3진단7일삭제·로그·TCP테스트·인계·최종리뷰/push/exactCI.
- v2질문재조회/명시적확인신호는현재공개DTO에없다. 임의로계약을확장하지않고인계공백으로기록한다. 기존전체10필드PATCH시험만으로질문별UI확인완료를주장하지않는다.
- 실패진단실제AI→Spring전송·권한·7일물리삭제·백업과운영로그는미검증. 합성모의삭제와실제삭제보장을구분한다.
