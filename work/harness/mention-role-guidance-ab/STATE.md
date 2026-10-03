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
