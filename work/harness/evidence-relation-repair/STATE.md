# 근거·관계 오류 분리 — 현재 E1·E2 오프라인 구현

## 현재 상태 (2026-10-01)

- 사용자 승인: E1·E2만 2시간 안에 오프라인 구현·검증. S1–S3 및 B 추가 반복 보류.
- 현재 브랜치 feature/candidate-evidence-audit, 계획 기준6cf018e.
- E1 3533cfd, E2 ed6c98b 구현 커밋. 위치 연결과 저장 응답 감사만 추가했다.
- A68/B68 보존, 인용 결함 A12(불일치2+다른 위치10)/B22(4+18) 재현.
- 원문4558자·132줄·후보68·rejected24·18개 원응답 보존. 원본22파일 해시 및 복사본 일치.
- field/status/verdict 변경0, 새 모델/API 호출0, 서비스 적용0. 큰 goal paused 확인.
- 신규 회귀26개 통과, 전체1329개 실행/1322 통과/7 skip/실패0.
- 최종 독립 검토 지적0. 원자료·복사본 대조 및 감사 재계산 일치. 결과 문서 완료.
- 이 요청의 구현·검증 완료(약25분). 구현 ed6c98b를 feature 브랜치에 push 성공 확인.
  종료 문서도 같은 브랜치에 기록한다. 다음 목표를 자동 시작하지 않는다.
- 자세한 기록: EXECUTION.md 및 specs/ai-developer/evidence-relation-repair/e1-e2-results.md.
- 결과 파일: E:/AgentFit/output/evidence-source-audit-v1/audit.json. 기존 원본은 변경하지 않았다.

## 이전 계획 단계 기록 (보존)

- 사용자 요청: B 추가 반복/서비스 적용 보류. 저장 응답만 분석하고 각각 수정안·회귀 계획 후 종료.
- 큰 goal: get_goal로 paused 확인, 상태 변경 없음. 새 모델/API 호출0, .env/key 미열람.
- 작업 폴더: E:/AgentFit/tmp/worktrees/document-input-runtime.
- 브랜치: feature/evidence-relation-plan, 기준 df5b1cc.
- 기존 dirty 보존: work/harness/semantic-confirmation-guard/STATE.md, STOP-20261001.md,
  .superpowers/, Docs/analysis/. 이번 커밋에서 제외.
- 입력: E:/AgentFit/output/direct-field-comparison-v1의 저장18응답·원문·68후보·gold10·전후 판정.
- 분석: 인용 결함 A12/B22(원문 불일치2/4, 다른 위치10/18). 정확한 인용이 있어도 보류 A12/B15.
  플랫폼/프로토콜을 외부 서비스로 보는 의미 오류와 인용 오류가 공존함을 원응답에서 확인.
- 핵심 위험: 근거를 위치로 자동 복구하고 과거 confirmed를 승인하면 Clean UI 같은 오확정도 해제됨.
- 설계: source pointer/문맥 단위와 semantic decision 분리. 외부 주장에 한정해
  supported_platform/uses_protocol/consumes_service/other/unclear 관계와 주어·술어·목적어 근거 기록.
- 원문 위치 복구는 과거 판정을 변경하지 않음. 새로운 관계 출력을 기존 모델 결과처럼 주입하지 않음.
- 산출물: specs/ai-developer/evidence-relation-repair의 analysis.md, spec.md,
  evidence-plan.md, relation-plan.md, regression-cases.md, audit.json.
- 신규 정답은 draft. 기존 승인10개/분모/점수는 그대로. 신규 E01–E10, S01–S14는 작성한 회귀 계획.
- 미실행: 제품 코드·실험 코드 수정, 새 테스트 구현/실행, 모델 호출, B 반복, 서비스·Spring·배포.
- 남은 단계: 문서와 원자료 불변 확인 → 이번 문서만 commit/push → 계획 보고 후 종료.

## 자체 검토·종료 준비

- 작성 문서5개+audit.json의 내용/인터페이스 대조 완료. 외부 관계 gate가 내부에서 참조 검증하도록
  명시했고, support는 subject/predicate/object 단위 합집합으로 통일했다.
- E01–E10/S01–S14 대조 유형을 문서로 작성. 아직 테스트 구현·실행이나 신규 gold 사람 승인은 없음.
- 문서 링크 누락0, 표 열 수 오류0, TODO/TBD0을 로컬 문서 검사로 확인했다.
- 입력/요청/요약/원응답22파일의 해시 재확인: 변경0. 실제 시작/응답 파일은 이전18개 그대로.
- 기준 df5b1cc 대비 ai_service, 기존 direct-field-comparison 코드/명세/결과 diff0.
- 완료 범위는 원인 분석과 두 계획 작성이다. 후속 구현·관계의 실제 모델 검증·서비스 적용은 미실행으로 남긴다.
- 이 문서 패키지만 feature/evidence-relation-plan에 commit/push하고 이번 요청을 종료한다.
