# SDD ledger — plan: specs/ai-developer/semantic-confirmation-guard/plan.md

BASE a375a13254d793c77b05d2ce448c29f6099810a7. 기존 branch CI 36815664857 success, tracked clean, .superpowers 보존.
Task 1: 조사 완료. 실제 PUBLIC-01 분류 오탐 2건, 기존 검토에서 제거됨. 정상 기능 6개 중 기존 분류 2개 누락, 검토에서 나머지4개 제거. 실제 Spring 저장 오탐 관측 없음.
Task 2–6: 아래 최종 갱신 참조. 초기 시험 결과는 재현 기록으로 보존.
Task 2: 의미 축/인용/서버 판정 6 tests GREEN. Task 3: 파이프라인/확인 metadata 4 tests GREEN. Task 4: 저장 이력3 + 실제HTTP1 GREEN, 기존 contract suite39 GREEN.
전체 unit1262: 1254 pass/7 skip/1 실패. 실패는 NVIDIA worker의 새 명시 옵션을 기존 호출 기대값에 반영하지 않은 테스트였고 수정했다. 최종 전체 재검증 예정.
1차 실제 비교8요청12호출, 오탐감소 있으나 정상 보류와 질문 증가로 미달. 모델 prompt/schema순서 가설만 바꾸어 2차 비교, gold와 서버 보수 판정 유지.
기존 source-validation-freeze는 코드 변경으로 preflight 거절됨. 그 파일을 갱신하지 않고 원문 해시를 직접 검증해 읽기 전용 진단에 사용했다. 새 API 비교는 별도 freeze를 작성한다.
공개 API 변경 없이 내부 모델 판단 메타데이터와 mock 승인 이력을 추가한다. 원본 평가 기준은 유지한다.
Ruling: 의미 분류는 opt-in 유지 — DeepSeek 실제 회귀에서 누락/질문이 증가하여 기본 경로 승격을 보류한다. 사용자 요청의 오탐 보호와 저장 분리는 구현하되 품질 개선 완료로 부르지 않는다. 비용: 기존 기본 분류의 품질 문제는 아직 남는다.
NVIDIA worker는 semantic_assessment=True를 명시하는 내부 호출에서만 새 분류 사용. 기존 HTTP 기본 모델/분류 변경 없음. metadata 수용·검증·승인 이력 분리는 항상 적용한다.

## 최종 갱신 2026-10-01

- 의미 축·정확한 근거·서버 보류 계약, opt-in pipeline/worker, v2 metadata, mock 사용자 승인 이력 구현 완료. SDD 결과는 comparison-result.md.
- 독립 리뷰 Important 3건 수정: sourceValue/documentId 정확 결합, other 질문 그룹 분리, draftSource/approval.source 고정. 수정 후 로컬 회귀 검증; 독립 재리뷰 미실행.
- 실제 GLM 실패를 회귀로 고정. 안내문을 deployment로 오분류해 Docker가 null 보류되는 현상은 여전히 품질 실패다. 후보 메타데이터는 저장까지 보존한다. 품질 기준을 낮추거나 정상값 보류를 성공으로 세지 않았다.
- 미분류 보류만 있는 pipeline이 candidate_profile을 내던 버그 RED 재현 → needs_confirmation으로 수정 GREEN. HTTP 저장에도 pending 질문 유지 확인.
- NVIDIA 36회(DeepSeek 24, GLM 12), 무료 확인 범위만/재시도0/대체0. 추가 모델 호출 종료. 고정 응답 재생은 로컬만.
- GLM 실제 비교(2회): 모델 오탐2→1, 정상 Profile 값 누락0/14→1/14, 질문2→2/회. 대조: 정상 누락0/10→0/10, 질문4→5/회, 보류4~5개. 기본 승격 보류.
- 최종 unit 1271건 중1264pass/7skip(66.164s), contract47pass(6.740s). logs final4. mock 의존성의 실제 응답 4건을 contract suite로 분리. 이전 final2의 Docker 포함 단언 실패는 실제 scalar 충돌이었다. 보존/보류 안전성 테스트와 품질 누락 지표를 분리하고 그 실패를 명시적 회귀로 남김.
- 기존 평가 JSON174 및 gold-v1 해시 보존, diff --check 통과. 원본 freeze/평가 기준 수정 없음.
- 남은 작업: 최종 문서/diff 검토 → feature 브랜치 commit/push → CI 확인. Spring/실사용/새문서 일반화/사용자 UI는 미검증. 전체 목표는 미완료.
