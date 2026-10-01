# 직접 필드 판단 비교 — 계획 작성 완료

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
