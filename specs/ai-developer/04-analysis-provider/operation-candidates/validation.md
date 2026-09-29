# 동작 후보 실험 검증 기록

## 사전 검증

- 새8개 단위 테스트와 관련11개, 총19개 통과. 최초7개 구현 부재 RED, 반려 항목의 병합 식별자 충돌1개 RED를 확인하고 각각 수정 후 GREEN을 확인했다.
- 전체876건 실행,870건 통과·6건 건너뜀, 종료 코드0. 로그: E:/AgentFit/tmp/operation-candidates-full-tests.log.
- 승인 H02 원본/추출 해시와 기존 후보125개 snapshot을 키 로딩 없이 preflight로 검증했다. 원본 해시 `2a290fff891ac850a03ea715629a8d9fef1fb1628776eec8e852c8175b2bb24d`, 추출 해시 `edb8447e18f9a8d29523ea7beb3f9aa76d78624414db2b7d80d88b1969b75b99`.

## 실제 실험 계획

기준은 candidate-field-semantics의 DeepSeek explicit-v1이다. 기존 분류 후보125개는 고정하고 새 동작 추출→독립 분류→원문 구간 병합→전체 분리 검토→최종 Profile 변환을 실행한다. 비교 대상은 새 후보의 원문 정확성, 반려 수, 최종 동작 표현, 문맥상 부정·검토안·이후 확장 범위다. 기존 sparse6개 검사는 부가 지표이며 전체 기능 정확도라고 부르지 않는다.

로컬 driver: E:/AgentFit/tmp/run-operation-candidates-h02.py. `--preflight`는 키를 읽지 않는다. `--live` 실행 결과는 E:/AgentFit/tmp/operation-candidates-h02-20260930-v1.json에 안전한 ID·위치·집계만 저장한다. PID·시작시각·stage·state를 추적한다. 결과가 있으면 덮어쓰지 않는다.

독립 리뷰·push·CI·실제 실행은 아직 미완료다. 전체 실사용 목표는 active다.

## 독립 리뷰 수정

P2 1건을 수정했다. other 정규화 전에 원본 status를 검사하지 않아 누락/미지원 enum/잘못된 타입이 정상 분류로 처리됐다. 5개 하위 사례에서 RED를 확인한 뒤 필수 키·타입·enum 선검증을 추가했다. 유효한 other 상태의 정규화는 유지했다. 관련20건 GREEN이다. 실제 문서 품질·전체 서비스 연결은 리뷰 범위 밖이며 별도 검증한다.

수정 후 전체877건 실행,871건 통과·6건 건너뜀, 종료 코드0을 확인했다.
