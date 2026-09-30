# 기능 후보 누락 가설 검증 상태

- Goal active. 직전 goal 턴은 진행률 보고로 no progress. 실제 Git/문서/freeze와 최신 보고 CI를 다시 확인하고 후속 실험을 시작했다.
- 작업 위치 E:/AgentFit/tmp/worktrees/document-input-runtime. feature/capability-candidate-recall, 기준 5fa61c9a1600f961b896aa3fe2718f1e3ea93fab. 기존 .superpowers와 worktree 보존.
- 직전 실제 평가22874는 exit0 terminal이며 재시작하지 않는다. 보고 CI36785513497는 동일5fa61c9 completed/success.
- 기존 안내의 capability nickname/heading label 회피가 짧은 기능 후보 누락에 기여한다는 가설을 검증한다. 원인 확정이나 품질 개선을 아직 주장하지 않는다.
- PUBLIC-09의 gold 기능3개는 Pro 안내, PUBLIC-01의6개는 기술 용도/1개는 당위형 소개다. gold는 유지하고 위치 도달과 의미 정답을 구분한다.
- 실험은 3문서×2안내, 최대18모델호출/3600초/재시도0. 무료 확인 만료 연장 없이 사용, 제공자 오류 시 중단. 새 개인정보 전송0, 유료0.
- 현재 명세/계획/새 안내 작성. 다음은 커밋→전용 임시 실행기/사전 점검→실제 비교→결과 판단·push. 기본 서비스 코드 변경0.
- 명세 사전 등록 df00419. 원래 freeze 사전 점검 exit0, 임시 실행기 로컬 안전 점검5/5 통과(외부0). 첫 점검의 Unicode 기대 위치를16→15로 바로잡았으며 제품 버그 수정으로 집계하지 않는다.
- 실제 비교 session94529 시작, 첫10초 관측에서 live 확인. 출력 E:/AgentFit/output/independent-profile-v1/capability-recall-spike-v1. 현재 스크립트·안내·소스 고정. terminal 확인 전 재실행하지 않는다.
- session94529 exit0 terminal. 6/6 요청,11모델호출,재시도0,요청시간합계150.199초. PUBLIC01등록위치0→0/7(새 안내46후보 전부 ambiguous_anchor),09 0→3/3(features/confirmed0),07 0→0/11. 원래 freeze와 기존84JSON 불변. audit.json 엄격 재계산·저장 완료.
- 결론: 명사형 기능의 회수는 개선됐지만 안내만 바꾼 상태는 채택하지 않는다. 다음은 긴 anchor 복사를 없애고 기존 일반 후보의 정확 인용 등장 위치 확장을 기능 추출에 적용하는 선택형 실험이다. 금지/다른제품/중복 문맥 독립 판단을 유지해야 한다. 새기획서일반화/사람정답/실제Spring 미완료. 이번goalturn은 실제 비교와 다음 원인 경계 확인으로 progress다.
