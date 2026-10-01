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
- 다음 재개: 직전 목표턴은progress. session91923을 재조회해live확인, 아직PUBLIC-01 결과없음. Win32_Process로 부모/자식46360과 제공자worker31196(00:52:08Z생성)을 확인했다. stream transport는별도worker를호출하므로 모델요청프로세스가새로생성된관측이며, 완료호출수/품질은아직미확인. 처음TCP검사는review부모에대한조회여서연결없음만으로호출중단을추정하지않는다. stdinpoll/파일/프로세스관측은호출재시작0이다.
- Docs/ai-profile-field-interpretation-review.md 작성, 사용자에게 기술목록의명시기능/지원Docker배포/ORMbackend범위를 질문했다. 답변대기; 전체gold사람검토와구분,기존gold/현재실험수정0. 질문은평가의모호한기준을분리하려는것이며독립작업은계속한다.
- 직전 goal turn verified wait(session91923 live), 이번턴 progress: GLM PUBLIC-01 완료19calls/1561.002627s. 기능4/4·Docker2/2유지,비기능2/2제외. 실제다른필드정확도/전체완료는아님. 나머지PUBLIC-07/SYNTHETIC실행중이며동일session91923마지막poll live. source/code/model/helper변경0.
- 기존finalizer사후외부0변환에서DeepSeekfeatures0→GLM4를확인,둘다needs_confirmation. deployment/database는null,여러배포방식에대한단일값계약이있는점기록. projection-public01.json과glm-partial-result.md저장. URL내부표현·중복과필드기준은사람확인/추가검토남음.
- 독립로컬timeout_probe.py:3초자식/1초timeout,부모1.023초timeout/4초시점marker없음. 외부0,현재평가에신호0,문제재현안됨. 현재child정리기능변경불필요. GLM에600초단위worker가생성되는것을확인했고중복실행0.
- 2026-10-01 재개: 직전 사용자 상태 답변은 session91923을 실제 재조회한 verified wait. 현재 같은handle live이며 PUBLIC-07이 valid14calls/1136.204573s로 완료, 기능14개 유지. 합성 실행 중. glm-partial-result.md 갱신, 이전 코드/자료/실행기 불변.
- API0 원문 대조: PUBLIC-01 C059(Email Templates)/C061(Internationalization)은 기술 용도 목록의 정확한 후보지만 other/irrelevant, C066/C069/C071/C073은 features/confirmed. 분류에는 explicit-v1만, 검토에는 추가 runtime-purpose 지침이 있다. 모델/지침 원인은 미확정. 기존173/36/16후보의 분류-only 두모델 비교를 classification-probe-plan.md에 사전등록 준비(최대18호출/10800초/0retry). 현재평가 terminal 전 실호출0.
- classification_probe.py·audit_classification.py를 별도 scratch에 준비, 제품코드0변경. 안전7PASS0.219s·집계2PASS0.390s/API0. freeze-classification.json 신규작성216d4778..., preflight6요청/18호출/결과폴더없음. PUBLIC-07 기존gold의 external_integrations는 partial, 명시기대3개(Airtable/Loom/Miro). GLM이 유지한나머지3개의외부제공자여부는미검증이며gold에없다는이유만으로오답단정하지않음. 다음현재GLM같은handle terminal→감사/결과push→분류비교실행.
- fafacc1 사전등록push완료. GLM session91923 terminal exit0:3건48calls/0retry/3730.348711s,합성16/16와제품명누락감지통과. audit_probe_glm.py --save exit0,사전비교모두통과/이전151JSON불변. glm-result.md/audit-glm.json작성. 목표는미완료:분류누락/필드해석/사람/새문서/Spring/운영남음. 다음결과push→분류preflight→실제18calls상한비교.
- GLM결과 d065a683ff8d9b4c246693dad717ba5867dcab1f push완료. 신규분류 preflight도동일freeze로유효함을재확인. classification_probe.py --live 실제 session38073 시작,같은handle45초조회live/아직첫결과없음. 91923은정상종료했으므로재조회/재실행하지않음. 현재 코드·후보·모델·분류실행기·계획·freeze동결,최대18calls/10800초/0retry/건별1800초. 다음38073계속조회→완료6rows라면audit_classification.py --save1회,실패면보존·진단하고재시작하지않는다.
- CI fafacc1 run36802513769 success. d065a68 run36802721659 최신조회는contract/core/unit success,integrated-runtime진행중이다. 제품코드는37e785a및이후CI통과코드와동일하며새로변경한제품파일0. 이번goalturn은progress:GLM전체감사·push와분류비교사전등록·안전검증·실행개시. 전체실사용목표완료아님.
- d065a683ff8d9b4c246693dad717ba5867dcab1f run36802721659 네작업success 직접확인. 실행checkpoint는6a9122e로push완료(상태문서만추가;해당SHA의CI는별도미확인).
- 분류session38073 첫PUBLIC-01-deepseek valid6calls/125.597819s. 지정6기능모두features/confirmed아님(기존누락2개복구0/2,기존4개보존0/4),비기능제외0/2,Docker2/2,이전라벨대비27개변화. classification_partial.py API0로읽고classification-partial-result.md에기록. 임시기준/단회진단이며현재GLM분류실행중. 새로작성한부분결과와상태는다음결과와함께commit/push예정. 현재분류코드/자료/plan/freeze변경0.
- 다음재개:직전goalturn은progress(GLM감사완료/분류시작). 동일38073 live를재확인,GLM첫행대기. 지정6기능의실제라벨은모두other/irrelevant이며가입·자체호스팅안내2개는features/confirmed. 과거분류의freeze/manifest대조와원문2개·분류핵심모듈5개hash동일을API0로검증하고classification-input-history-audit.json저장. 과거rawpayload미보관이라완전요청동일성/원격비결정성은미확정. .github/workflows/ai-linux.yml의push paths에work/**가없어상태전용6a9122e는실행대상이아님을확인. 마지막제품/명세변경d065a68의CI4개는성공.
- 728c23f4f02213b4d07f9121938aa568dea4093a push/CI36803718000 네작업success. 분류38073 terminal exit1:GLM세번째호출600.008s미완료/PROVIDER_STOPPED. 계획대로후속4요청미시작,9attempt/8transportcomplete/917.173499s/0retry. audit_classification_failure.py --save exit0/이전159JSON불변. underlyingcode는기록되지않아PROVIDER_TIMEOUT단정하지않음. classification-result.md보존. 현재모델실행0;38073재실행금지.
- 다음한정진단classification-batch-probe-plan.md작성:실패30후보C060..089를15개두묶음으로,각DeepSeek/GLM동일조건총4호출/2640초/0retry. 기존안전오류메타데이터계약사용,제품코드0변경. helper작성·안전검사·새freeze·push후에만호출. 전체실사용목표active.
- classification_batch_probe.py 준비. metadata는기존analysis_call_metadata계약을재사용하고providererror를고정코드로보존. classification_batch_selftest.py6PASS0.354s/API0. 새freeze acf933a21c900067ac71ab490b39163d8d7da09152766f19e0fbe0c1673852a1,preflight4요청/4호출/결과폴더없음,제품파일변경0. 현재원격모델실행0,남은NVIDIAworker0관측. 다음실패감사와15후보계획push→preflight재확인→단회실행.
- f3daf2293c41e3616daae489daf78ebbf7a39045 push,CI36805182061 네작업success 직접확인. 15후보실험classification_batch_probe.py --live session38637 시작. 마지막45초poll live,현재3요청완료(A-deepseek,A-glm,B-deepseek),B-glm실행중. A첫묶음 지정기능DeepSeek4/5(10.064622s),GLM5/5(69.625513s). classification-batch-partial-result.md작성. 전체30후보/173후보/최종서비스품질판정아님.
- 현재동결:제품모듈/기존c·p실행기/새classification_batch_probe.py/계획/freeze/모델/자료변경금지. classification-batch15-probe-v1 결과폴더사용중,기존38073·91923은terminal이므로재실행0. 다음같은38637 terminal확인→audit_classification_batch.py --save단회(성공/실패모두지원)→결과보존·push. 부모timeout이면시도호출수미확인으로남김. _fetch가이미read1을써서고정크기read대기가설은수정근거없음.
