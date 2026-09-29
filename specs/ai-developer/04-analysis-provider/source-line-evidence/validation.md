# 원문 줄 ID 기반 근거 계약 검증 기록

## 구현 전 근거

- 고정 공개 PRD 5건의 첫 평가에서 Solar 기본 구성과 문맥·병렬 구성 모두 자동 완료 0건이었다. 안전 진단에서 최초 core 또는 features의 `QUOTE_NOT_FOUND`·`QUOTE_NOT_IN_CONTEXT`·`VALUE_NOT_IN_QUOTE`가 반복됐다.
- 기존 `repair-context-options`는 첫 추출 이후 수정 요청에만 선택지를 제공한다. 이 실험은 최초 추출부터 quote/context 생성 필드를 제거한다.

## 로컬 구현 확인

- opt-in `LineEvidenceSolarAnalyzer`는 core, features, 수정 요청에 `{value,lineId,role}`을 사용한다. 서버가 선택한 줄에서 정확 값의 유일한 위치를 구하며, 없음·중복·줄 ID·역할·상태 오류를 거부한다.
- Profile 반환 구조·의미 검토·기존 복구형 확인 질문 경로를 유지한다. 기본 `SolarAnalyzer`의 스키마는 변경하지 않았다.
- 단위·모의 Provider 테스트에서는 CRLF·Unicode 위치, 반복 문자열 거부, 명시적 없음, 오류 필드 수정, 실패 초안 보존, 안전 진단 버전·오류 코드, CLI opt-in을 확인했다.
- `python -m unittest discover -s tests -q`: 로컬 599건 통과. 라이브 Solar 호출과 Linux CI는 아직 실행하지 않았다.

## 미해결

- 모델이 정확한 `value`조차 복사하지 못하면 `VALUE_NOT_IN_LINE`으로 보류된다. 구조적 오류 감소나 의미 정확도 개선은 실제 PRD 튜닝 실행 전에는 입증되지 않는다.
- 원문 줄 전체를 의미 검토에 제공하지만 Profile 근거 span은 값 자체의 위치다. 상태를 나타내는 주변 문맥의 해석은 의미 검토 결과에 의존한다.
- 새 독립 문서, 실제 사용자 확인 부담, Spring/Frontend 저장 E2E는 별도 검증이 필요하다.
