# 저장 응답 회귀 자료

`saved_pair.json`은 승인된 공개 linkding 문서 평가의 입력·요약 및 18개 원응답을
UTF-8 문자열 그대로 보존한다. 문서 전체와 A/B 68개 후보·판정·원응답이 들어 있다.
출처는 `output/direct-field-comparison-v1`, 사전 고정 해시는
`specs/ai-developer/evidence-relation-repair/audit.json`이다.

원문 위치 변환은 없다(Unicode code point `[start,end)`). 문자열을 UTF-8로 인코딩하면
원본 바이트와 일치한다. 외부 경로나 네트워크 없이 CI에서 읽을 수 있다.
요청 payload와 freeze 파일은 중복 프롬프트의 크기를 줄이기 위해 fixture에서만 제외했다.
실제 오프라인 replay는 그 두 파일을 포함한 원본 22개 모두 해시 검증·보존한다.

테스트가 기대하는 결함 ID/12·22 집계는 기존 audit.json에 고정된 기준을 읽으며
새 감사 코드에서 기대값을 계산하지 않는다. 기존 field/status/verdict는 수정하지 않는다.
