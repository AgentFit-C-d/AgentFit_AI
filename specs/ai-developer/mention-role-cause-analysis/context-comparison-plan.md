# 고정 역할 지침의 새 합성 문맥 비교

## 승인 범위 / 실행 전 고정

2026-10-03 사용자 요청. B는 `E:/AgentFit/output/mention-role-guidance-ab-20261003-v2/B-role-instruction.txt`의 바이트를 그대로 재사용한다. 기존 freeze의 SHA256과 대조한다. A는 현행 MENTION_ROLE_INSTRUCTION과 이전 A가 동일한지 검사한다. 다른 system 내용·모델·출력8192·temperature0·thinking=false·schema·서버판정 유지. 새 후보ID enum과 문서 입력만 새 자료에 맞춘다. 각 문서 내 A/B 차이는 역할 블록 하나뿐이다. 전체 원문과 ±240자 문맥·ID·Unicode 반열림 위치를 동등 제공한다. 기대값/해설은 모델에 보내지 않는다.

합성 문서·별도 기대값은 `work/harness/role-context-ab/cases.json`. 모델 응답 전 확정한 별도 평가 기준으로, 기존 AgentFit 40개 의미 골드는 변경하지 않는다. 사람이 검토한 실제문서 골드나 자연분포 표본이라고 주장하지 않는다.

## 사전 기준

| 문서 | 후보 | 기대 field | mentionKind | 상태 | 범위/판정 근거 |
|---|---|---|---|---|---|
|D1|C000 LatticeDesk|project_name|other|confirmed|대상 이름|
|D1|C001 웹 서비스|project_type|other|confirmed|제공 형태|
|D1|C002 연구 장비 예약 관리|domain|other|confirmed|명시한 문제 영역|
|D1|C003 PebbleBoard|project_name 또는 other|other|irrelevant|다른 제품 예시, scope=other|
|D1|C004 OrionID|other|other|irrelevant|설정 파일의 호환 대상 이름, non_product|
|D1|C005 OrionID|external_integrations|external_service|confirmed|실제 인증 제공자|
|D1|C006 OrionID|external_integrations|external_service|confirmed|공식 SDK 데이터 제공자|
|D1|C007 OrionID|external_integrations|external_service|negated|외부 백업 연동만 부정. 인증/데이터와 다른 관계|
|D2|C000 HarborLedger|project_name|other|confirmed|대상 이름|
|D2|C001 모바일 앱|project_type|other|confirmed|제공 형태|
|D2|C002 재난 물품 배분|domain|other|confirmed|명시한 문제 영역|
|D2|C003 PineQueue|project_name 또는 other|other|irrelevant|다른 제품 예시, scope=other|
|D2|C004 NimbusGate|other|other|irrelevant|설정 출력 수신 Client 이름|
|D2|C005 RiverPass|external_integrations|external_service|confirmed|공식 SDK 인증 제공자|
|D2|C006 RelayWave|external_integrations|external_service|tentative|현재 릴리스의 채택 검토, commitment=proposed|
|D2|C007 VaultMesh|external_integrations|external_service|tentative|동일 릴리스·로그인 관계의 긍정/부정 결정 미해결|

정상 긍정9발생위치, 명백한 범위 밖4, 명시 부정1, 미정/상충2. 둘째 문서에서 다른 제공자의 명시적 SDK 채택은 상충 대상 제공자의 미정과 별개다. 다중 제공자는 양립 가능하며 단독 제공자라는 요건이 없다. 다른 제품명은 field=project_name/scope=other와 field=other 두 표현 모두 허용한다. 미정의 polarity와 상충의 commitment는 단일 enum을 강제하지 않고 cases.json의 허용값으로 비교한다. 상충은 선택 후보를 포함한 긍정 근거와 명시 부정 구간의 counterEvidence를 요구한다.

## 측정

- 후보별 raw field/mentionKind/modelStatus/5의미축/conflictsChecked/support/counterEvidence와 실제 서버 판정 보존.
- 역할·필드·상태 오류 각각 측정. 유효필드 confirmed 오답과 field=other/confirmed 조합 오류 분리.
- 정상 긍정의 supported/보류/제외 및 정확한 supported, 서버 통과 오답, 올바른 범위 밖 제외, 올바른 명시 부정, 미정/상충 raw 판단과 실제 보류를 각각 집계.
- quote 부재·occurrence 오류·후보 미포함을 의미오류와 분리. 같은 후보의 여러 인용 결함은 후보수에서 중복계수하지 않는다.
- tentative/proposed가 excluded되는 현행 서버 문제는 고치지 않으며 raw 모델 오류와 분리한다.
- 합성 오프라인 응답은 안전장치/채점 검증에만 쓰고 실제 모델 점수에 넣지 않는다. 두 arm이 완료된 문서만 A/B 효과 비교한다.

## 안전 및 실행

1. 로컬 자료/요청 동일성, 비밀정보 기록 차단, 원문 위치, 의미/인용 별도 채점 검사.
2. 공유 전송 gate: D1 A→B, D2 B→A. 전 문서 합계 최대4회, 재시도0, 기존 무료 NVIDIA DeepSeek만 허용.
3. 전체1220초에서 종료20초를 제외한 단일 전역시계. 매 전송은 min(600초, 남은 작업시간-0.05초). 문서가 바뀌어도 예산 초기화하지 않음. 기존 subprocess transport가 진행 중 요청 timeout 시 자식프로세스를 종료함. 첫실패/시간초과/옵션오류/해시변경에서 다음 전송 금지. 중복 실행 marker를 독점 생성.
4. 검증: 모든 실패 위치1~4, 부분pair, 전역시간 축소·만료, 실자식프로세스 종료(짧은 시간), 파싱/schema/모델 오류, 비밀정보, 재시작/다섯번째 호출 차단. 외부 네트워크 차단.
5. 독립 읽기 검토 및 로컬 검증 통과 후 실제 실행 파일·원문·후보·기대값·A/B 요청·옵션·코드 커밋을 새 output 폴더에 동결. 최초 전송 뒤 변경 금지.
6. 지정4회 범위에서 실행하고 결과/한계 보고 후 종료. 최종 Profile 품질·실제 문서 일반화·반복 재현성의 증명 아님.

분석 로직/서비스 상수/프롬프트 B 추가수정/40의미골드/서비스 적용/Spring/GLM/추출/큰 Goal 재개는 범위 밖.
