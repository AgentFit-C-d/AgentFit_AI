# 구현 계획

1. 기본 분석기 진단과 평가 도구의 허용 목록·집계 테스트를 작성하고 실패를 확인한다.
2. `solar.py`의 검토 예외 처리에서 고정 사유만 호출 진단에 기록한다. `default_service_quality_baseline.py`의 허용 목록 투영·사유별 집계를 연결한다.
3. 관련·전체 테스트를 실행한다. 이전 형식 오류 사례를 같은 기본 설정과 `low` 선택형 설정으로 제한 재평가한다.
4. 재현된 사유와 수정 가능 범위, 미재현 여부를 `validation.md`에 기록한다.
5. 변경 파일만 커밋하고 `feature/default-review-validation-reasons`를 push한다.
