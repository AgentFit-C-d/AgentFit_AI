# 오탐 보완 구현 계획

Spec: spec.md. 직접 순차 구현, 기존 worktree 재사용, feature/semantic-confirmation-guard. 사용자 최신 구체적 수정 요청과 목표의 자율 실행 범위에 따른다.

1. 실제 사례/대조 사례를 고정하고 단계별 원인을 기록한다. 원본 해시와 기존 출력은 변경하지 않는다.
2. 의미 분류 계약·원문 인용 위치·서버 판정 회귀 테스트 RED → 구현 GREEN. 불완전/중복/외부 ID, 반복 위치, 모호/상충과 정상 요구사항을 포함한다.
3. NVIDIA 분석 연결과 confirmation-v2 메타데이터 전달 테스트 RED → 구현 GREEN. 기존 기본 Solar 및 공개 Profile/OpenAPI 유지. 내부 모델 판단을 사용자 승인 상태로 승격시키지 않는다.
4. mock 사용자 승인 이력 분리 테스트 RED → 구현 GREEN. 저장 실패, 재분석, 버전 충돌, 권한, 수동 수정/확인, 모델 메타데이터 위조를 검사한다. Spring 인계 문서 작성.
5. 입력·평가 조건을 고정한 최대12회 무료 비교 실행. 오탐/누락/확인 요청을 함께 기록하고 API 실패는 성공으로 계산하지 않는다. 진단용이며 출시 판정이 아니다.
6. 관련/전체 테스트, 원본 보존 검사, 전체 변경의 독립 리뷰, 수정·재검증 후 기능 브랜치 commit/push. 배포·merge 없음.

## 인터페이스

- classify_grounded_candidates → labels + modelDecisions. labels는 기존 필드/status 계약. modelDecisions는 모델 주장과 서버 결정/근거 위치를 보존.
- finalize 결과의 선택적 modelDecisions → project_candidate_confirmation → HTTP → gateway → mock review. metadata 없는 이전 응답도 유지하되 모델 확정 근거를 추정해 만들지 않는다.
- MockStore.confirmation_provenance(owner, project) → 현재 초안의 모델 기록과 별도 사용자 승인 스냅샷. 테스트/인계용 내부 메서드이며 공개 API 확장이 아니다.

## 완료 기준

실제 실패 사례의 최초 오분류 단계와 후속 경계를 설명하고, 안전 조건/사용자 승인 분리 회귀를 통과한다. 실제 모델 비교에서 감소 여부를 사실대로 보고한다. 오탐 감소와 실제 서비스 적용 가능성은 별도로 판정한다.
