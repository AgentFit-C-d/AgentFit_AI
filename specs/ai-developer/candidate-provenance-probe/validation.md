# 후보 누락 진단 검증

## 범위

프로덕션 `agentfit_ai`와 원래 freeze는 변경하지 않았다. 새 코드는 `diagnostic_tools`의 관측기·격리 worker·3문서 runner이며 기본 서비스에 연결하지 않는다. 외부 모델 호출 없이 합성 응답과 로컬 HTTP/SSE로 검증한다.

## 확인한 증거

- Task1 RED: 신규 모듈 부재로 8테스트/9실패. GREEN: 8통과. 정수 위치·ID·enum·단계 순서·길이·반복 위치·null/빈 배열·전체 확인 승격 사유와 원문 비노출 검증.
- Task2 RED: worker8실패/runtime4실패. GREEN: worker7통과/Windows symlink 생성권한으로 1skip, runtime4통과(15.528초 task-done).
- 실제 SDK 합성 제공자 비교: 원래 worker와 진단 worker의 payload·결과·호출 단계/수가 동일. provider 검토/기능 정리 실패 때 관측 prefix만 남으며 timeout/cancel 때 자식과 연결이 종료된다.
- Task3 RED: 신규 runner 부재로 10실패. 초기 구현의 호출 수 집계가 존재하지 않는 totalCalls 키를 사용한 오류를 실제 metadata 계약의 calls 길이로 수정했다. 최종 집중 검증 11통과(3.917초).
- Task3 검증은 코드/자료 불변성·메모리 자료 변조·부정한 sidecar·기존 출력 보존·취소·무료 범위/만료/예산·제공자 오류 중단·로컬 CLI와 합성 env loader를 포함한다. golden 정답은 부모 채점에만 사용한다.
- 실제 고정 자료의 오프라인 preflight 통과: PUBLIC-01/09/07, 도구4파일, 기존 freeze `f5e1f64b667a075046680182dba86456417af1894304916813377e61ccd3eba5` 불변. 키 로드/실제 API0.

## 회귀 검증

전체1280건 중1274통과/플랫폼skip6. unit1201건 중1195통과/skip6(65.856초, session44166 exit0), runtime35통과(123.831초, session5019 exit0), contract36통과(6.487초), core8통과(27.779초). 모든 그룹은180초 상한 안에서 끝났다. .superpowers의 이 계획 전용 verification-unit/runtime/contract/core.log에 전체 로그를 보존했다.

## 한계

로컬 Python에 기존 platform-prefix 경고가 있고 일부 asyncio 테스트는 slow-callback 진단을 출력한다. Windows에서 symlink 생성 자체를 못 하는 테스트는 통과로 집계하지 않는다. Linux CI는 push 후 별도 확인한다.

실제 문서 진단·누락 원인 확정·품질 개선은 아직 미실행이다. 새 기획서 일반화·사람 검토 정답·사용자 수정 부담·실제 Spring/운영 검증은 이 도구의 테스트 성공으로 완료되지 않는다.
