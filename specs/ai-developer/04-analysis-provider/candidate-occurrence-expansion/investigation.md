# 조사 기록
현재523b23a 기준 반복 이름의 정확한 인용도 ANCHORED_CANDIDATE로 거부된다. test_coverage_ambiguity_and_duplicates가 이를 요구하므로 기본 경로를 유지해야 한다.
anchored_analysis.py는 span을 판정 입력에서 제거한다. 위치별 문맥 없이 동일 문자열을 여러 ID로 늘리는 것만으로는 충분하지 않다.
judgment_schema는 이미 후보 ID별 판정을 요구하므로 기존 응답 형식과 호출 단계를 재사용할 수 있다. merge_profile의 중복·충돌 거부는 유지한다.
조사에서는 로컬 재현만 수행했고 외부 API 호출이나 서비스 코드 변경은 하지 않았다.
