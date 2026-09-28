# 진행 상태

- 목표: 후보·판단은 Solar Pro4로 유지하고 의미 검토·재검토만 다른 모델을 쓰는 선택형 경로를 구현·평가한다.
- 사용자 후보: DeepSeek V4.1 Flash, GLM 5.3, Kimi K3. 기본 서비스와 공개 Profile은 유지한다.
- 브랜치: `feature/semantic-review-model-routing`.
- 완료: SDD 명세·계획, NVIDIA 어댑터 확장, 단계별 라우팅 테스트, 세 모델 합성 호환성 검사, DeepSeek와 Solar 20건 교차 평가.
- 결과: 1차 DeepSeek 8/20 대 Solar 5/20, 2차 DeepSeek 7/20 대 Solar 6/20. 2차 DeepSeek는 검토 시간 초과·형식 오류 각 1회, 의미 검토 거절 6건, 다구역 지정 사실 3/27 대 Solar 6/27. GLM·Kimi 합성 검사는 각각 40초 시간 초과. 기본값 미변경.
- 다음: 최종 전체 테스트, 코드·결과 보안 점검, 관련 파일만 commit/push. 인과 효과 확인에는 같은 후보·판단 출력을 공유하는 후속 평가가 필요하다.
