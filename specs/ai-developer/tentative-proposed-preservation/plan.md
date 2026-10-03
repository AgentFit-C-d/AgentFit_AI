# 최소 수정·검증 계획

1. 이전 output/role-context-ab-20261003-v1 자료를 별도 fixture로 복사한다. 원문·후보·raw응답·이전서버결과·B·기존골드 해시를 보존한다. 이전 _decision 본문을 테스트 참조로 보관한다.
2. 기존 validate_assessments 재생이 저장 서버결과와 동일한지 확인하고 RelayWave의 제외 사유가 commitment!=adopted임을 기록한다.
3. tentative/proposed의 명시적 범위 밖/부정/과거 등을 먼저 제외하는 기존 판정순서를 유지한다. 마지막 commitment 차단만 좁게 분리하여 일치하는 역할의 tentative/proposed를 needs_confirmation으로 반환한다.
4. 테스트: 실제 A/B2행, 전체32행 불변/변화, 정상confirmed, 제외조건중첩, 근거/역할/상충, 모든enum조합 차등비교, v2/v3 최종 경계의 보류와 원문위치·긍정값거부. 합성 boundary packet은 coverage_verified=False 및 모든 필드 unresolved, 실제 검토응답 주입0.
5. 전체 unit suite와 요청한 기존 v3/위치회귀를 외부 통신 차단하여 실행한다. 환경/플랫폼상 실행불가 검증은 별도 보고하며 skip/기준완화 추가0.
6. 실행전후 원시응답/지침/기존골드 무변경을 검증하고 결과만 로컬 커밋한다. 사용자가 이번 작업에서 외부 네트워크 전송을 금지했으므로 push는 하지 않는다.

예산: 모델0/외부네트워크0/재시도모델0. 로컬 작업 목표2시간, 테스트 subprocess당600초. 큰Goal재개0. 승인된 작은 수정으로 별도 재승인 불필요.
