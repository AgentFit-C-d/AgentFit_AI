# 독립 Profile 평가 상태

## 최신 상태 — 2026-09-30 사용자 비용 조건에 따라 실제 평가 중단

- 사용자 목표 변경: 실사용 범위는 입력→분석→사용자 확인·수정→Spring 저장의 핵심 흐름이다. 새 기능 확장보다 완결성, 실패/시간초과/재시도/중복/버전 충돌, 민감 로그 차단 및 삭제 정책 검증을 우선한다. 아래 이전 전체목표 범위는 이 지침으로 대체된다.
- 외부호출 조건: NVIDIA 현재 계정에서 추가요금 없는 모델·엔드포인트임을 확인한 경우만 가능. 무료 여부 미확인 또는 무료 한도 소진 시 중단, 유료 전환/충전/모델 대체 금지. 재시도도 같은 조건이다. Solar 유료 호출 별도 승인은 없으므로 현재 Solar 포함 고정 기준선은 재개하지 않는다. 개인문서 전송·운영 배포도 별도 승인 필요.
- 89953에 Ctrl-C 전달 후 exit1 확인. check-evaluation-processes.ps1에서 평가 runner/worker0개 확인. 완료1개(PUBLIC01/run0 ANALYSIS_FAILURE,247.598초), 중단1개(PUBLIC01/run1 started-only)를 보존했다. 중단행을 모델 실패/성공으로 임의 기록하거나 재호출하지 않는다. 실제 평가 종료 여부는 검증됐으며 목표 자체를 pause한 것은 아니다.
- Spring 접근은 사용자가 현재 제공불가로 확인했다. 현재 API 계약을 기준으로 mock 서버/계약 테스트를 진행하라는 명시적 승인. 실제 Spring 연동은 미검증 유지, 요청·응답 형식/추후 연결 검증 항목을 인계한다. 사용 가능한 조직 저장소 조회 결과 AI1개뿐.
- 다음: 별도 feature/core-analysis-contract-tests에서 비용0 로컬 mock·계약 테스트를 SDD로 구현. evaluation production117와 evaluator6파일·모델·원문·골드는 보존. 실제 평가 Task3는 incomplete, 전체리뷰/30회결과 미완료다.

## 이전 실행 상태 (중단 전 관측)

- 직전 상태 보고 turn은 no progress. 이번 재개에서 Git 변경과 실제 파일을 대조하고 SDK 통합 검증을 진행했다. 전체 실사용 목표는 active/미완료다.
- Task1 최종 HEAD ebcb9e9b6df0502f07d3f1f71533308f4b7b8a90; 원격/CI36717146470 일치 증거는 E:/AgentFit/tmp/independent-profile-task1-remote.json. 아래 초기 기록은 이력이다.
- Task2 worker/protocol/process/preflight/checkpoint 구현. 관련21개 테스트 통과, 실제 SDK·로컬 HTTP/SSE 테스트2개 RED→GREEN(2.594초). CLI --live 없이 키/파일 읽기 금지 테스트 추가.
- 실제10문서/207골드 사전검증 통과. 원래 production117파일 불변. evaluator SHA256 8d6ab064551419943e18732dd5ba96763f8cbb1faeb029ec4470f6dd78f70f49. 모델 API 실행0회.
- Task2 최종 da49dfb278787174bd35fa4fe777e7242ae4324d 커밋/push. task-done ebcb9e9..da49dfb,1117개/5skip(48.072초), runtime11개(40.310초). handle19183/30640 종료0; CI36720782159 동일SHA·두 작업success.
- Task3 시작 BASEda49dfb. 실제30회 평가 exec handle89953 살아 있음. 결과 E:/AgentFit/output/independent-profile-v1/runs-baseline-da49dfb. 13:26UTC 관측1/30완료: PUBLIC-01/run0 failed ANALYSIS_FAILURE247.598초, gold24/missing24; run1 진행 중. 다음 관측은 같은 handle89953 write_stdin 및 .superpowers/sdd/plan-independent-profile-evaluation/live-status.py. 상태 파일만으로 종료를 추정하거나 다시 실행하지 않는다.
- 직전 goal turn은 progress(Task2 구현/검증/push/CI·실제평가 시작). 이번 재개는 같은89953 live확인·첫실패수치확인·오류전달경로 조사. 서비스가 pipeline stage/detail을 출력하지 않아 provider_code없는 오류는 ANALYSIS_FAILURE로 합쳐진다는 관측 한계 확인. 첫실패 원인/단계는 미확인; 현재코드 고정 유지, 사후 단계별 안전진단 보존이 다음 조사후보.
- 현재 frozen117+새평가기6개 코드 수정 금지: 다음 실행의 사전검증을 깨뜨린다. 자료·골드도 고정. 다음: 30terminal 수집→집계→Task3 전체리뷰1회→검증/push. 테스트 통과만으로 제품 사용 가능성을 주장하지 않는다.

## 이전 기록

- 전체목표:실사용가능AI,계속active/미완료. 직전goalturn은progress:통합서비스구현·독립리뷰C0/I0/M0·push9af3f2a·exactCI36712248884success. 재개시clean과외부CI메타데이터일치확인.
- 작업:기존isolated E:/AgentFit/tmp/worktrees/analysis-runtime,신규feature/independent-profile-evaluation,base9af3f2a9bcd47d5e3bb40860fe674434787b442a.
- 발견:예약PUBLIC04는이전Immich와동일sha27b511...,PUBLIC05는기존ActualBudget계열. 예약10개를독립10개로세면오류다. 원래manifest보존,평가세트에서제외/공식다른계열2개교체.
- 현재:source/config freeze 이후 공개본문10개 검토, 신규PUBLIC11 Outline/PUBLIC12 Paperless 확보. 사전골드207단위/29제외/12모호성,100필드 검토. agent-authored/human_reviewed=false, 모델API0. 원본본문이나 모델응답은 Git/결과에 기록하지 않음.
- Task1 구현:independent_evaluation_corpus.py(계열/해시/경로/골드 검증),independent_profile_evaluation.py(정확한 위치 채점). 반복인용·오분류·중복·빈배열·null·실패분모 보존. 모호/미등록 출력은 unassessed,실사용통과 항상false. frozen production117파일 해시 모두 불변.
- 검증:baseline1073 tests/5skip(49.936s),focused21 RED→GREEN(0.041s);1094 tests/5skip(47.637s),runtime9pass(46.560s);실제10source/gold validator통과. 최종 전체리뷰는 Task3후1회,현재 미실시.
- 골드:E:/AgentFit/output/independent-profile-v1/gold-v1.json,sha5fcdc3a15fdbd346e0e351313639c1ebe2cac02cc36f33abf749d2ff22caa283. 자료의 ambiguities/partial은 미확정 역할을 감추지 않기 위함. Cal.com/Cal.diy 동일계열 처리.
- 다음:Task1 커밋/task-done 후 Task2 worker/runner TDD,합성 실제SDK 검증,사전해시고정후실제10×3평가. 살아있는API평가handle 없음. 중단checkpoint만으로실행종료/재실행추정금지.
- Task1후속수정:다른필드골드매칭만으로known_wrong추론금지,명시적wrong_role제외만오답. 추가회귀RED→GREEN22/22. 초기f83ea0b push/CI36716424167는구버전;수정HEAD의전체gate/CI완료를재개시확인해야한다. SDD초기Task1complete만으로최신수정완료를추정하지않는다.
- 최신확정:Task1 codeHEADbc3ae4e,1095tests/5skip(41.105s)/runtime9pass(38.883s),task-done9af3f2a..bc3ae4e. 이전완료이후수정까지검증됐다. Task2인터페이스·정확wire·CLI/프로세스/checkpoint테스트 요구는plan에확정,아직구현미착수. 최종원격HEAD/CI는E:/AgentFit/tmp/independent-profile-task1-remote.json에기록예정이며파일존재/현재원격을재확인해야한다.
- 사용자자율설계/계획/실험승인과featurepush/직접구현유지. 질문반복하지않음. metadata seen=false는실제과거노출근거보다우선하지않는다.
- 남은전체요구:모델의미품질/독립사람골드/수정부담,실제Spring확인저장/버전경쟁/실패원본7일삭제,배포환경. 공개README평가만으로완료아님.
