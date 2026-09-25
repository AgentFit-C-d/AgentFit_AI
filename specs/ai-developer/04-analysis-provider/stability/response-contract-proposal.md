# 내부 응답 구조 개선안 — 승인 및 구현 완료

## 근거
동일한 profile-v3 프롬프트의 고정24회 평가:
- medium: 14통과, 10시간초과.
- low: 17통과, 5시간초과, 2 UNKNOWN_HAS_EVIDENCE.
- none: 16통과, 8 UNKNOWN_HAS_EVIDENCE.
추론 끔에서는 응답은 받았지만 별도의 data/evidenceQuotes 맵이 모순될 수 있었다.
세 실험의 모든 결과는 별도 JSON에 보존한다. 이것은 명확한 구조 결함이며 모델 내부 사고 원인을 단정하지 않는다.

## 제안하는 변경
현재 Provider 응답은 data와 evidenceQuotes가 각각 10키를 갖는다.
새 내부 응답은 10개 필드 각각을 아래 두 형태 중 하나로 제한한다.

```json
{
  "project_name": {
    "value": "예시 이름",
    "evidenceQuotes": ["프로젝트명은 예시 이름이다."]
  },
  "database": null
}
```

예시는 두 필드만 표시했다. 실제 Schema에는 10개 필드를 모두 필수로 둔다.
각 필드는 null 또는 value/evidenceQuotes object로만 구성한다. 알 수 없는 필드는 null이므로 근거를 붙일 위치가 없다.
known 값의 타입·비어 있지 않은 근거·고유한 원문 인용·기존 Profile 검증은 유지한다.
Provider adapter가 기존 data/evidence 구조로 변환한다. Spring 전달 Profile·DB·HTTP 경계는 바꾸지 않는다.
유효하지 않은 응답을 정답으로 고치거나 의미를 추정하는 후처리를 추가하지 않는다.

## 변경 파일과 확인 항목
- solar.py: Provider Schema/Prompt/내부 변환. 외부 AnalysisResult/Profile은 유지.
- test_solar.py: 새 Provider 모양, null 변환, 잘못된 known 객체 거부, 근거 검증 회귀.
- 신규/기존 fixture의 정답은 그대로 둔다.
- 최종24회 평가를 새 report에 수행. 실패 보존, 모든10필드 및 이름을 함께 비교.
- Prompt 변경이므로 새버전(profile-v4). 적절한 추론 설정은 실측으로 선택하고 실패 없는 평가 전 채택 완료로 표시하지 않는다.
- API의 null/object Schema 수용성을 profile-v4 실제24회 호출로 확인했다.

## 승인 상태
사용자가 “내부 응답 구조 개선 진행”으로 승인했다. 구현 후 실제 API가 새 Schema를 수용했고 고정24회 모두 통과했다. validation.md 참조.
