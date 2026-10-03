# Role guidance A/B — comparison-plan.md

- 2026-10-03 사용자 승인: 동일8후보, 현행 A/계획문구 B만 교체, 무료 NVIDIA DeepSeek 최대2회, 재시도0. 전체1220초/요청600초/종료20초, 첫 실패 중단.
- 큰 Goal paused. 기존 worktree 재사용, feature/mention-role-guidance-ab, 기준a3fc12f. 기존 unrelated dirty 보존.
- 단계: 독립 payload/제한 장치 작성 → 오프라인 검증/동결 → A/B 새2호출 → 고정채점과 보고 후 종료.
- 서비스 상수·분석·schema·모델·골드·복구worker 수정0. GLM/추출/전체Profile평가/사용자확정/Spring저장/배포0.
- Ruling: 승인된 한 쌍의 비교 실행이므로 기존 work/harness 기록을 SDD ledger로 유지한다. 별도 거대 구현 플랜/새 워크트리는 만들지 않는다. 기존 실행기의 단일 요청 SSE subprocess/응답parser를 재사용한다. 재현 자료 보존 요청에 따라 ledger/실험폴더는 삭제하지 않는다.
- 무료 근거: 현재 사용자가 앞서 확인한 NVIDIA endpoint로 이 정확한 두호출을 승인. 계정 quota 독립 조회 없음, 별도 시험 호출/유료 대체 없음.
- 중단: 로컬 preflight 테스트 11개가 setUp의 임시 디렉터리 생성에서 실패. `E:/AgentFit/tmp/worktrees/document-input-runtime/tmp`가 없어 FileNotFoundError [WinError3]. 테스트 본문의 제한/종료/채점 검증은 실행되지 않음.
- setUpClass의 build_package는 오류 없이 반환했으나 이것만으로 전체 검증 통과를 주장하지 않는다. 정식 freeze/live는 실행하지 않았다.
- 사용자 조건 ‘실행 전 로컬 검증이 실패하면 호출 전에 멈춤’에 따라 이번 실제 호출0, A/B 둘 다 미측정. 재시도/자동 설정 변경/추가 실험 없음.
- 평가 실행기·테스트만 준비됨. 제품 코드/지침/schema/골드 변경0. 다음 승인 작업의 최소 수정은 테스트용 임시 디렉터리 생성 또는 기존 유효 경로 지정 후 전체 preflight 재검증이다. 이번에는 수정·재검증·실제 호출을 하지 않고 종료.

## 2026-10-03 후속 승인에 따른 재개

- 사용자가 실험 내용/제한을 바꾸지 않는 로컬 준비 오류 수정과 재검증, 통과 후 A/B 실제 호출을 승인했다. 큰 Goal은 여전히 paused.
- 수정: 테스트 setUp에서 부모 tmp를 mkdir(exist_ok=True) 후 고유 prefix의 TemporaryDirectory 생성. 새 임시 경로가 테스트 root 아래인지 확인 후 자신이 만든 임시 자료만 정리한다. 기존 파일 삭제/덮어쓰기 없음.
- 초기 중단 v1 폴더는 보존한다. 실제 비교 산출물은 새 v2 폴더에 기록하도록 OUTPUT 경로만 변경. 모델/지침/후보/정답/schema/판정/600·1220·20초/2회 제한 변경0.
- 전체 기존 preflight 11개 통과(0.427초). 단축 모의 시계/실제 대기 자식프로세스 종료, 첫 전송/파싱/검증 실패 중단, 중복실행 방지, 동일성/채점 검증을 모두 실행했다. 모델/네트워크0.
- 다음: 새 경로 포함 최종 검증과 읽기 전용 검토 → 로컬 코드 커밋 및 실제 파일/요청 동결 → 승인된 단일 A/B → 보고 후 종료. 초기 실패와 이번 수정은 각각 보존한다.
- 독립 검토에서 저장 안전 P2 발견: Unicode escape로 표현된 합성 키는 원시 문자열 검사 후 저장되고 기존 parser에서 나중에 거부됐다. OFFLINE 합성 키 회귀 테스트가 응답파일 존재 assertion에서 실제 실패(RED), 초기 로그와 함께 별도 보존했다.
- Ruling: 저장 경계에서 기존 NvidiaAnalyzer/parser를 이미 받은 bytes만 반환하는 로컬 transport로 재사용하여 디코딩된 민감값 검사까지 파일쓰기 전에 수행. 새 모델 전송/해석규칙/schema/서버판정/시간·호출제한 변경0. 민감값을 기록하지 않는 기존 조건을 실행기의 로컬 저장 경로에 적용하는 최소 수정이며 사용자 허용 범위로 판단했다. parser 미통과 응답 본문은 디스크에 저장하지 않고 실패 코드/안전한 진단만 남긴다.
- 최종 preflight 12/12 통과(0.486초), 검증 조건 완화/skip 없음. encoded key의 envelope와 내부 content 두 경우 모두 파일저장 전에 거절되고 후속 B 전송이 차단됨. 실제 모델0. 로그: E:/AgentFit/output/mention-role-guidance-ab-preflight-20261003-v2/final-tests.txt.
- 독립 검토 제외 항목 판단: 계정 잔여량 별도조회는 승인된 두호출 외 요청이므로 하지 않음. 실제 정확도/일반화는 이번 한쌍결과 범위만 보고. 디스크I/O까지 강제종료하는 별도watchdog은 추가하지 않으며, subprocess 요청 제한과 남은 전체 전송 시간 검사를 유지하고 실제 경과시간을 보고한다.
