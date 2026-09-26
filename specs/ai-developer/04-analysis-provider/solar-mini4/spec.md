# Solar Mini 4 비교 실험
사용자 승인: Mini로 변경해서 실험. 공식 API https://console.upstage.ai/api/chat 확인: solar-mini4 및 solar-mini4-260922, Pro4와 같은 reasoning_effort 및 json_schema 지원.
모델만 변경하고 section-v2 프롬프트/입력/정답/6회·60초/출력토큰 제한을 유지한다.
모델 선택은 생성자에서 지정하며 모든 추출/통합/검토/수정 호출에 적용한다. 기본 모델은 기존 Pro4로 유지하고 이번 실험은 Mini를 명시한다.
응답 모델명을 정확히 기록한다. 미지원 모델 설정은 호출 전에 거절한다. 공개 Profile과 실패 원본7일 정책은 유지한다.
완료: 전체 회귀 테스트, 고정 후보 개별 검사, 기존7사례 평가, 정답/오답/오류/지연 보고, feature 브랜치 push.
단일 반복의 소규모 비교는 일반 성능 우열의 증명이 아니다.
