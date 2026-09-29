# 구현 계획

1. `test_public_holdout.py`에서 정답 위치와 다른 정확 인용을 `indeterminate`로 기대하는 실패 테스트를 작성한다. 값이 없는 span은 여전히 오류인지 함께 검증한다.
2. `_citation_state`가 정답 anchor를 찾은 뒤 다른 근거 span의 정확한 값 포함 여부를 검사한다. 정답 구간 일치가 우선하며, 모호하거나 대체 근거인 경우에만 판정 불가로 처리한다.
3. `SCORE_VERSION`을 `public-evidence-v3`로 올리고 버전 회귀 테스트를 갱신한다. 기존 산출물은 수정하지 않는다.
4. 전체 테스트와 안전 평가 산출물을 확인한다. 실제 문서 재실행은 확률적 모델 출력의 한계를 명시한다.
5. feature 브랜치 push와 Linux CI를 확인하고 검증 기록을 남긴다.
