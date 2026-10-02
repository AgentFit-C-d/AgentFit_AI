# 상태

- 목표: 진단 적용 현재 코드로 LS 기존 16후보 D/G 각 2배치, 최대 4회 비교.
- 브랜치: feature/localsend-model-comparison, 진단 기반 f0bdc04.
- 승인: 현재 사용자의 동일 무료 엔드포인트 신규 4회 지시. 재시도 0, 첫 실패 중단.
- 보존: 지침/스키마/원문/후보/정답/서버 판정 고정. FR 호출 0, 서비스 적용 0, 큰 goal 중단.
- 완료: 명세·계획, LS 실행 게이트, 신규 로컬 테스트 5개 통과.
  전체 1,393개 실행: 1,386 통과 / 7 skip / 실패 0 (70.205초).
- 근거: E:/AgentFit/output/localsend-model-comparison-preflight-tests.log.
- 독립 검토: LS 동일 요청/정답, 상한·중단·동결 유지 승인. 서비스 소스 f0bdc04 대비 변경 없음.
- 실행 코드: 591965bd0b436371d41f0cef071ec9c250906b3d. 228개 동결, 실행 후 manifest 포함 229개 확인.
- 실제 결과: D1 성공 → G1 성공 → G2 성공 → D2 INVALID_RESPONSE에서 중단. 총4회, 재시도0, FR0.
- 실제 실패: HTTP200, text/event-stream, sse.event index1, error.code500 / Internal server error.
  발췌87바이트, 26.886초. 공급자 내부의 더 구체적 원인과 이전 실패의 동일 원인은 미확인.
- 품질: GLM16개 완료(주15), 오확정3/서버통과3, 정상누락0/6, 제외6/9, 보류0, 인용결함0.
  DeepSeek8개만 관측: 오확정1/통과1, 정상누락0/2, 제외5/6, 보류0. 나머지8개 미평가.
- LS07: 양쪽 features/negated/excluded. LS15: D미평가, G confirmed/supported 및 상충230줄 미선택.
- 자료: E:/AgentFit/output/localsend-model-comparison-v1 (freeze/summary/verification/audit/calls).
- 감사: 요청4개 동일, 원시판정24개 보존, 입력/과거 결과 해시264개 확인.
- 보고: specs/ai-developer/localsend-model-comparison/results.md.
- 종료: 첫 실패 후 추가 호출/튜닝 없음. 결과 commit/push 후 종료, 큰 goal 중단 유지.
- 기존 타 작업 변경: semantic-confirmation-guard STATE/STOP, Docs/analysis, .superpowers 미접촉.
