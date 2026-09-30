# 독립 Profile 평가 검증 기록

## 2026-09-30 — Task1 자료·정답·채점기

- 분석 production117파일 LF 정규화 SHA256은 사전freeze와 동일하다. 모델/프롬프트 변경 없음.
- 기존 예약10개 중2개는 이전노출로 제외. 남은8개+공식 고정commit Outline/Paperless2개로10계열을 구성,원본파일해시·UTF8·크기 검증 통과.
- 10문서/100필드 원문검토,사전골드207단위·29제외·12모호성. 별도의 사람 검토 없음. gold hash `5fcdc3a15fdbd346e0e351313639c1ebe2cac02cc36f33abf749d2ff22caa283`.
- baseline:1073 tests,1068pass/5skip,49.936s.
- 새 회귀:21개 모두 기능 부재로RED후21/21GREEN(0.041s). 원문 위치 유일매칭/반복·중복/미등록/부재/실패 분모/출처·골드변조를 검사한다.
- 전체:1094 tests,1089pass/5skip,47.637s. 실제SDK 로컬통합9/9,46.560s. 외부모델API0.
- 이 기록은 채점기 동작 검증이다. 새 문서에 대한 모델성능 결과는 아직 없고,의미precision/recall·수정부담·독립사람정답·Spring저장·운영완료를 증명하지 않는다.
- 초기커밋f83ea0b를 feature/independent-profile-evaluation에 push했다. 이후 자체검토에서 다른필드등록만으로오답추론하는 위험을 발견해,명시적wrong_role제외만오답으로 세도록 수정했다. 회귀22개중1개RED→22/22GREEN(0.035s). 이 수정의 전체검증과 정확한 원격CI는 후속 기록으로 확인한다.

## 남은 작업

- Task2 실제 통합worker/기한/typed출력/중복방지checkpoint 구현 및 검증.
- Task3 30terminal결과,필드별누락/명시적오류/미채점 분리,독립전체코드리뷰,push/exactCI.
