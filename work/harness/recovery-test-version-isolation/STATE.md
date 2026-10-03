# 복구 테스트 버전 격리 상태

- 큰 Goal paused 확인. 기준10b8d02, 새 branch feature/recovery-test-version-isolation.
- 기존 dirty semantic-confirmation-guard STATE 및 untracked .superpowers/Docs/analysis/STOP 파일은 보존.
- 원인: tests/test_review_recovery.py의 ROOT가 최신 checkout으로 고정되어 같은 버전 동작 검사도 CODE_MISMATCH에서 차단. 서비스 inspector의 거부는 올바른 동작.
- 방향: 기존20개 case를 hash-검증한 snapshot Python 프로세스에서 실행하고 결과를 개별 전달. 현재 버전의 구 기록 거부는 별도 테스트.
- 원본 zip에 실제 실행코드147개·Python3.13.3바이너리·패키지4개 조건 포함. review_recovery inspector는 실행 후 추가된 도구이므로 현재의 변경 없는 파일을 별도로 복사, frozen service code와 구분.
- 모델/외부전송/실제재개0. SDD spec/plan 작성. 다음: 초기 hash 기록·실패 재현, 테스트 격리 구현.
- 원본/제품/지침/계약 보호파일370개 hash를 output/recovery-test-version-isolation-20261003-v1/protected-before.json에 보존. 초기 복구20테스트 재현:2failure9error(CODE_MISMATCH),9pass, skip0.
- 테스트 본문을 recovery_preserved_cases.py로 이동. 각 테스트 setUp에서 matching verify_runtime을 먼저 성공시킨 뒤 원래 결함 조건 실행. 분리 프로세스에 snapshot147개를 그대로 복사·검증, 현재의 변경없는 복구검사기만 별도로 복사. 부모에20개 결과 각각 전달.
- 일차 복구22테스트20기존+2버전회귀 전부 통과. 원문·구 코드·해시·원래20개 test 본문/기대값은 그대로.
- 결과 전달 회귀에서 자식 subtest exception이 failure로 집계되는 문제를 RED 재현후 error로 구분해 수정. 해당1테스트 GREEN. 서비스 변경 아님.
- 전체unit/runtime/core-flow/contract 테스트 실행 중. 읽기 전용 독립리뷰 진행 중. 모델/실제복구0. 초기 patch의 동일파일 move+add 도구오류는 분리 적용으로 해결, 테스트 의미·제한 변경 없음.
- 첫 전체 회귀1503:1492pass/7skip/4xfail/예기치않은실패0. runtime39/core8/contract47 모두통과. 보호370파일/원래20test본문 AST 동일확인.
- 리뷰에서 RTK 없는LinuxCI의 자식launcher 의존성 발견. PATH=''에서FileNotFoundError RED 재현후 테스트 내부 shell=False 자식은 절대sys.executable 직접 실행하도록수정. 셸도구호출은계속RTK사용. 해당버전3테스트26.714초모두통과. 원본20케이스를PATH없는환경에서도실제로실행했고skip0.
- 최종 전체unit 재실행 중(새 launcher회귀 포함1504예정). 제품/fixture/기대값변경0. 독립리뷰후속진행.
- 최종unit1504개137.515초:1493pass/실패0/오류0/skip7/기존xfail4. 복구·버전·launcher·전달24개모두통과, 기존복구20개는기본격리와PATH비운실행각각20pass0skip. 실제LinuxCI미실행.
- 최종verify_artifacts: 보호370파일·기존20test본문AST무변경. 서비스/진단검사기/원본fixture/CI설정gitdiff없음. 리뷰지적RTK의존성해결 재검토완료, 추가발견없음.
- 결과문서 specs/ai-developer/recovery-test-version-isolation/results.md. 기록 output/recovery-test-version-isolation-20261003-v1. 다음은 이번파일만로컬커밋후종료. 큰Goalpaused, 모델/외부전송/실제재개/배포/Spring저장0, push안함.
