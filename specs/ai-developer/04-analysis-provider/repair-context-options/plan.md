# 근거 문맥 선택지 구현 계획

**목표:** 원문에서 서버가 만든 구별 가능한 문맥을 수정 모델에 제공해 위치 오류를 줄이는 opt-in 실험을 만든다.

**구조:** 별도 `repair_context_options.py`가 안전한 선택지를 만든다. Solar의 기본 no-op hook을 통해 복구형 분석기만 수정 data에 선택지를 추가한다. 기존 응답 스키마와 검증기를 그대로 사용한다. 공개 튜닝 평가 CLI에 선택형 스위치를 노출한다.

**파일:** `ai_service/agentfit_ai/{repair_context_options.py,solar.py,recoverable_solar_analysis.py,public_holdout_evaluation.py}`, `ai_service/tests/{test_repair_context_options.py,test_recoverable_solar_analysis.py,test_public_holdout.py}` 및 이 폴더의 검증 기록.

## 작업 1: 후보 생성

- [x] 두 번 등장하는 이름에서 정확하고 서로 다른 문맥이 나오는 실패 테스트, CRLF·한글 테스트를 작성한다.
- [x] 없는 인용·9회 등장·중복된 동일 문맥·비위치 오류의 후보 생략 테스트를 작성한다.
- [x] `build_repair_context_options(document, errors, previous)` 구현 후 테스트를 통과시킨다.

## 작업 2: opt-in 분석기

- [x] 가짜 Provider로 수정 payload의 후보·시스템 지침, 기존 opt-out 동일성, 반환된 잘못된 문맥의 거부를 실패 테스트로 재현한다.
- [x] `SolarAnalyzer._repair_correction` no-op hook과 복구형 opt-in override를 구현한다. 후보는 기존 correction에 `evidenceOptions`로 추가한다.
- [x] 관련 테스트 통과. 기본 `SolarAnalyzer`, Profile, 호출 수는 불변이다.

## 작업 3: 평가와 결정

- [x] 공개 평가 CLI에 `--repair-context-options`를 추가하고 plan에 설정을 기록한다.
- [x] 한국어 튜닝 문서에서 1회 관찰 후 기준선과 다른 모델 실행이라는 제한을 명시한다.
- [x] 전체 테스트·diff check·feature 브랜치 push·Linux CI를 확인한다. 완전성·지연·오확정 게이트를 통과하기 전 기본값 활성화는 금지한다.
