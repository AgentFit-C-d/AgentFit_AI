# SDD ledger — plan: specs/ai-developer/docling-text-layer-preservation/plan.md

- 목표 active. 직전 goal turn은 progress: OCR 품질0/2 계측·원인 분리·DOCX구조 추출·62be915 push. 활성 변환/API세션 없음. 기존 결과를 재실행하지 않는다.
- Base62be91504a33f6df705f93973d6cd24ed022621c. linked worktree E:/AgentFit/tmp/worktrees/document-input-runtime, branch feature/docling-text-layer-preservation. tracked clean, 기존 .superpowers 보존.
- 명세/계획 작성. 사용자 SDD·자율 실행·feature push 승인 유지. 구현 직접, 리뷰1회. 기본서비스 변경/배포/모델호출0.
- Pre-flight: 단일 Task, 공유 인터페이스 충돌 없음. 원래 어댑터와 호출부/테스트를 읽었고 export/iterate 기본 body만 사용함을 확인했다.
- Windows에서는 POSIX helper 대신 이 ledger에 BASE·단계·실행 결과·리뷰 범위를 직접 기록한다. 스크래치/기존 결과는 삭제하지 않는다.
- Task1 시작: baseline 관련 테스트 → 회귀 RED → 최소 수정 GREEN → 실제 SDK/캐시/전체 검증 → 독립 리뷰 → push.
- Baseline: analysis-runtime 관련9tests OK/2skip. RED: 기존코드+새테스트15개에서7assertion실패/3skip; 실제DoclingDocument 회귀1개도 머리말누락으로실패. GREEN: 경량15tests OK/3skip, 실제SDK단일회귀1pass.
- 수정: 고정5layer를 export/iterate에 동일전달. document.texts가list인지/모든텍스트객체가순회됐는지대조, 누락PDF_PARTIAL_TEXT. 기존표/반복/페이지검증유지. 추가SDK강제import없음.
- Optional session30647 terminal: 실제 테스트 자식exit0,39tests OK30.732초. 부모출력은cp949 진행률문자표시실패exit1; 저장된testlog/result.json으로테스트성공확인. 모델API재실행없음.
- Cache replay: 고정 mixed JSON hash eed102dd... 유지, 머리말1회복구·페이지offset통과·213자. 기존FastAP!오인식/부정누락은남음, 과거품질0/2변경없음. E:/AgentFit/output/docling-text-layer-preservation-v1/replay.json.
- 원문10·검토문/대응10·이전JSON174·gold불변재검증통과. 전체 unittest session61740 terminal exit0:1252실행/1245통과/7skip,75.688초(부모77.266초). 현재활성변환/API세션없음.
- Task1 구현검증완료, 최종독립리뷰대기. 리뷰범위base62be915부터 현재기능커밋까지. 알려진제약은OCR품질/Docling이이미버린native텍스트미검출/실제Spring미검증. 이번수정으로최종품질gate통과를주장하지않음.
