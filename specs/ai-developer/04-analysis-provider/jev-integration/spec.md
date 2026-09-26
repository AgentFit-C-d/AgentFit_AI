# Jev 구역 분석 통합 실험
사용자 승인: Jev를 기존 분석기에 연결해 같은7사례 평가.
## 범위
opt-in jev_merge로 기존 Mini4 통합/의미수정 호출을 Jev choice 호출로 대체한다.
추출과최종검토는 Mini4, 추출prompt 및 입력/정답은 이전 Mini4 평가와 동일.
후보ID당 selected/not_current/not_confirmed/wrong_role/duplicate/conflict 중1판정.
전체원문과 서버검증된후보를 state로 전달하고 질문별로 후보ID를 명시한다. 선택확률을 정답확률로 보장하거나 임계값으로 자동수정하지 않는다.
역할/범위/확정상태/중복/충돌/근거 기존검증은 유지. Jev가 기존검증을 우회하거나 새 값을 만들 수 없다.
최대6호출/60초 공통예산 유지. 빈 후보풀은 통합API를 생략하고 null초안을 검토한다.
Jev불가/오류 시 자동fallback없음. 기존 기본분석기 미변경.
## 평가
같은7문서로 정답/오답/오류와 실제 Jev 도달 건수를 구분.
추출단계 실패는 Jev 판정성능 평가로 해석하지 않는다.
기존12합성 역할분류와 후보 통합은 다른 과제다.
공개Profile 유지, 혼합실행의 result.model은 기존규칙에 따라 unknown이며 호출별모델로확인.
실패raw7일보관과성공raw미보관을 유지.
