# Solar Profile 분석 작업

- [x] T001 Spec·Plan·Tasks와 사전 정답 범위를 정의한다. 경로: specs/ai-developer/04-analysis-provider/
- [x] T002 [US1] ai_service/tests/test_solar.py에 정상·근거 위치·Unicode 테스트를 먼저 작성한다.
- [x] T003 [US2] ai_service/tests/test_solar.py에 입력·HTTP·응답·Secret·중복 근거 실패 테스트를 작성한다.
- [x] T004 [US1] ai_service/agentfit_ai/solar.py에 strict schema·Prompt·인용 위치 변환·기존 검증기 연결을 구현한다.
- [x] T005 [US2] ai_service/agentfit_ai/solar.py에 고정 API 전송·크기 제한·redirect 차단·안전한 오류를 구현한다.
- [x] T006 [US3] ai_service/tests/fixtures/solar-cases.json과 ai_service/agentfit_ai/evaluate.py로 합성 6건을 평가한다.
- [x] T007 전체 단위 테스트 및 실제 결과를 specs/ai-developer/04-analysis-provider/validation.md에 기록한다.
- [ ] T008 관련 파일만 커밋하고 feature/solar-profile-analysis를 push한다.

의존: T001 → T002/T003 → T004/T005 → T006 → T007 → T008.
SDD는 기존 기능별 폴더에서 수행하며 전역 .specify/feature.json은 다른 전체 Feature를 가리키므로 변경하지 않는다. 자동 Spec Kit CLI 전체를 실행했다고 표시하지 않는다.
