# 직접 필드 판단 비교 — 승인된 한 쌍 준비

## 최종 상태 — 완료 후 중단

- 2026-10-01 승인된 A→B 한 쌍만 실제 실행: 시작18/반환18/실패0/재시도0. 각68후보 완료.
- 정답10개 기준 A→B: 모델 유효필드 오확정제안4→4, 서버 통과 오확정4→3,
  정상 누락4/6→2/6, 주 평가 보류2→3, 전체 보류24/68→37/68.
- 정상 기술 linkding/Django/JavaScript 복구. Firefox/Chrome·PWA 오류 잔존,
  태그 정리 기능은 근거 제목만 인용해 새로 보류. Clean UI 감소도 동일 근거 부족 차단 효과.
- 시간 A963.162초/B546.719초. 공통 변환 이후 정상 누락도4→2. 모든 후보 기록 보존.
- 점수 밖58개를 방식명 가린 뒤 검토: OIDC 오필드 양쪽 잔존, B 정상 기능2개 추가 보류,
  반복 이름·배포·개발 문맥 경계는 사람 검토 필요로 분리.
- 결론: 부분 복구 신호는 있지만 사전 기준 미통과. B 그대로 채택하지 않음.
- 최종1303테스트(1296pass/7skip), 비교 전용14테스트. 고정 응답 검증과 실제18호출 구분.
- 사후 verification: 동결 파일 변경0, user message9쌍 동일, NVIDIA 설정 동일.
- 결과 specs/ai-developer/direct-field-comparison/results.md 및 results.json.
- 전체 원자료 E:/AgentFit/output/direct-field-comparison-v1 보존. 추가 모델 호출 없음.
- 큰 goal paused를 도구로 재확인. 서비스/Spring/배포/Luna 미변경·미실행.
- 후속 반복은 사용자 결정 전까지 보류. 이번 구현·결과 기록 commit/push 후 종료.

## 2026-10-01 최신 상태

- 사용자: 제시 정답 승인. 무료 NVIDIA 최대18회, A→B 한 쌍만 실행한 뒤 결과 보고·종료.
- 브랜치 feature/direct-field-comparison, 기준11ba918. 서비스/큰 goal/Luna 재개 범위 밖.
- 문맥: 저장 원문4558 code points 전체 + 후보별 앞뒤240 code points, 후보68개·순서·batch8 동일.
- A 기존 다축/의미 역할 분류; B 직접 필드·상태·근거. 공통 로컬 Profile 투영까지 관측.
- 무료 근거: 기존 사용자의 현재 계정 무료 API·초과 시 무결제 거절 확인과 유효 기록.
  DeepSeek V4.1 Flash / integrate.api.nvidia.com/v1/chat/completions, 만료2026-10-01 17:32:45 UTC.
  계정 과금 화면을 독립 조회한 것은 아니다. 매 호출 전 scope/기간/입력·코드 해시 검증.
- 실제 전송은 thinking=false, temperature0,8192토큰. 템플릿의 reasoning_effort는 NVIDIA adapter가 제거.
- comparison.py/evaluate.py는 서비스 밖 실험. 호출 시작을 먼저 저장, 전체18회, 재시도0,
  최초 provider/schema/free/identity 오류 후 전체 중단, 불완전 실행 점수 null.
- 로컬 TDD: 도구 없는 RED → 10테스트 GREEN. 전체 모의 흐름 추가 후 직렬화 오류 RED →
  로그 scalar whitelist 및 실제 Profile evidence 경로 사용 → 12테스트 GREEN.
- 현재 실제 호출0. 전체 로컬 회귀와 독립 리뷰 진행 중. 검증 후 해시 동결·한 쌍 실행 예정.
- 결과·원응답은 E:/AgentFit/output/direct-field-comparison-v1에 독립 보존 예정. 기존 자료 수정 없음.
- 이전 계획 기록은 아래에 보존한다. 이후 현재 상태 기록이 우선한다.

### 구현 검증 기록

- 첫 전체 suite: 1301실행,1294통과,7skip. 모델 API 없는 로컬 테스트.
- 독립 정적 리뷰: P2 오류 사유 손실1건. 무료 미확인/입력변경/기한 및 응답 계약 실패가
  일반 PROVIDER_FAILURE/ValueError로 보이던 문제를 안전한 allowlist 코드로 보존.
- 회귀2건 RED 확인 후 GREEN, 비교 전용14테스트 통과. 최종 전체 suite 재실행 중.
- 리뷰에서 18회 제한·동일 문맥·첫 오류 중단·부분 채점 금지의 추가 중요 문제 없음.
- 계정 무료 조건의 독립 조회나 실제 모델 품질을 로컬 테스트가 입증하지는 않는다.

### 한 쌍 실행 시작

- 최종 전체 suite 1303실행,1296통과,7skip,82.661초. 비교 전용14건 포함.
- freeze 완료: 독립 output의 freeze.json에 원문5파일·입력·payload18개·정답·코드·무료기록 해시 보존.
- live 명령 1회 시작. 시작 marker로 동일 출력 위치의 재실행 금지. 최대18회·A→B 순서.
- API key는 전송 함수 내부에서만 사용하고 출력·로그·Git에 기록하지 않는다.
- 실행 중 코드·원문·정답·모델·batch 변경 없음. 결과 확인 후 이 상태에 완료/중단 결과를 덧붙인다.

## 이전 계획 작성 기록

- 사용자 범위: CI 확인, 실패 시 이번 변경 문제만 수정, 동일 저장 후보/문맥의 비교 계획과
  검토용 정답 기준 작성 후 종료. 비교 구현/실행 지시는 아직 없음.
- CI run36841277590 / head075c07e: completed/success, 네 job 모두 통과. 코드 수정 필요 없음.
- 기존 dirty 상태: semantic-confirmation-guard STATE/STOP, .superpowers, Docs/analysis 보존.
- 브랜치: feature/direct-field-comparison-plan, 기준6dea756.
- 큰 goal: 도구로 paused 재확인. 새 모델 API 호출0. 키/.env 미열람, Luna 미재개.
- 사실: 저장 linkding 원문4558자, 후보68개/rejected24개, before/after grounded 완전 일치.
- 산출물: specs/ai-developer/direct-field-comparison/{spec.md,plan.md,gold-review.md,input-manifest.json}.
- 정답: 요청6사례+대조4사례 초안, human_reviewed=false. PWA 경계 및 점수 밖58개 처리 검토 필요.
- 비교: A현재다축분류, B직접필드/상태/근거. batch8와 전체원문/각240자문맥 동일.
- 이후 제안 예산: 3쌍×방식당9호출=최대54회, 재시도0, 무료 확인된 NVIDIA만.
  이는 실행 결과/현재 호출 승인이 아니다. 정답 검토와 이후 실행 지시 전까지 중단한다.
- 지표: 원모델/서버 통과 오확정, 정상 누락 사유, 보류(전체/정상), 기록 유실, 호출 수, 시간 각각 보고.
- 미실행: 새 분류기/평가 도구 구현, 실제 비교, 서비스 연결/배포/Spring 변경.
- 남은 사용자 결정: gold-review 정답·PWA 매핑 검토. 이번 범위는 계획 전달 후 종료.

## 문서 확인

- manifest의 기존 자료5개 해시 전부 일치, 68개 후보/24개 거절 및 전후 grounded 일치 재확인.
- 주 정답10개 ID·원문 범위·줄 번호 대조 완료(pytest 줄 번호는94로 바로잡음).
- ai_service의 기준6dea756 대비 diff 없음. 이번 새 파일은 계획/정답 검토/manifest/상태 문서뿐.
- 실제 평가 수치·B모델 정확도는 아직 없음. 과거 결과를 새 A/B 결과로 표시하지 않았다.
- 계획 문서 push 후 이번 요청 종료. 정답 검토와 후속 실행 지시 전까지 구현하지 않는다.
