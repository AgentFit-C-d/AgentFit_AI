# 필드별 검토 상태

- 목표 active. 직전 목표 턴은 progress: 고정사유 재현과 두규칙 비교56호출을 완료, source/gold/이전결과 보존·c0338d8 push.20703/41153/5657 종료,현재 모델 요청0.
- feature/field-local-candidate-review, 기존 linkedworktree 재사용, main아님. 명세·계획 작성, 사용자 자율 승인과 직접 구현방식 유지.
- Task1 필드별 검토→Task2 bool opt-in 연결. 공개 API/default 변경0. 로컬180초/suite, 실제평가는review/CI이후별도등록93호출5400초/retry0/무료확인.
- 다음: 계획전용ledger/brief→Task1 RED→구현→검증→Task2→독립최종review1회→push/CI. 실제품질·새문서·사람·Spring·운영 gate 미완료.
- Task1 모듈 부재 RED→8/8 GREEN. 240개 fixture 계산 오류(221+9)를231+9로 수정, production 원인 아님. unit1229건 중1223pass/6skip64.241초, session63284 exit0. 실제API0. 다음Task1 commit/task-done→Task2.
- Task1 baddd566f477535f1bb81b9f6b717d45e0fe5951 complete, task-done8/8. Task2 옵션미지원 RED7tests/12errors→GREEN7/7. 최종 unit1230pass6skip65.922초(session3774), runtime35pass124.848초(session79271), contract36pass6.938초, core8pass28.107초(session11777), 모두exit0. 합계1309pass/6skip. 실제모델0. 다음Task2commit/task-done→독립최종review1회.

- 2026-10-01 재개: 직전 상태 답변 턴은 no progress. 실제 HEAD20587d9/기능브랜치/추적파일 변경0 확인. 기존 완료 평가 재실행0. 독립최종review Critical0/Important0/Minor0, focused15PASS; 전체로컬로그1309pass6skip 확인. review.md에6개 판단유보영역과 실행결정 기록.
- 검토-only3건 평가 사전등록, helper6PASS0.020s, freeze 신규생성. 다음 docscommit/push→exactHEAD Linux CI→free/preflight재검사→실제평가 동일handle추적. 실제모델 호출 아직0.

- 2026-10-01: a9ab774 push/CI36796417954 네작업성공. 실제session2563 exit0,3건48호출0retry0실패228.156743초. 이전143JSON불변. 기능0/4,Docker0/2,공개07기능14/14,합성16/16이나project_name누락놓침. 품질미달로기본적용보류. 새모델실험전결과감사저장.
Ruling: GLM 비교는 모델별 기존adapter설정까지 포함해 해석한다 — DeepSeek와GLM의temperature/추론설정이이미다름 — 가중치만의효과로오인할위험을막고입력/지침/스키마동일성을검증한다.

- GLM 사전등록8e2962f push. safety6PASS0.020s, offline48요청 쌍의 원문/후보/지침/스키마동일 확인. 차이는 model/temperature/reasoning_effort/chat_template_kwargs. freeze782f4d3f09d9a8e262749c061f28403cb615431830a6385b9d4f31c1b1e62d59.
- 실제 GLM session91923, 2026-10-01T00:41:43Z 시작. 00:43 이후 같은handle live 확인, 아직PUBLIC-01 결과없음. 요청1800초/전체5400초/93호출/retry0. 실행중 코드·모델·자료·실행기 변경 금지. observation timeout은 실패가 아니며 같은handle 재조회. 다음 terminal 후 audit_probe_glm.py --save, 실패면 재시작하지 않고 보존·진단.
- 8e2962f961198aaff7f65253e0b23895ed69f0b1의 CI36797418498 네 작업 success 직접확인. 이후 state만변경, 제품코드/평가기동결유지. session91923 마지막40초poll도live/신규출력0. 이번목표턴 progress: 실제48호출진단·감사·push·CI완료와 GLM비교개시. 목표완료아님, 다음턴같은handle계속조회.
