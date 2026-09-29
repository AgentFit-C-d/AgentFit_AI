# 구현 계획

1. `ai_service/tests/test_default_service_quality_baseline.py`에 성공·실패 진단 투영과 원문 비노출, 단계 집계 테스트를 추가하고 실패를 확인한다.
2. `ai_service/agentfit_ai/default_service_quality_baseline.py`에 진단 허용 목록 투영 함수와 단계 집계를 구현한다. 기존 결과 형식은 추가 필드 외 유지한다.
3. 관련 테스트·전체 테스트를 실행하고 20개 합성 사례를 Worker와 동일한 설정으로 한 번 평가한다.
4. `validation.md`에 시간 초과 단계와 분포, 정확도·검증 오류, 평가 한계를 기록한다. 이어지는 수정 가설은 실측 근거에 맞춰 선택한다.
5. 변경 파일만 커밋하고 `feature/default-service-stage-timing`을 push한다.
