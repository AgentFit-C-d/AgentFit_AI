# Solar 응답 제약 추가 튜닝
사용자: OpenAI 비교 취소, Solar 튜닝 계속. OpenAI API 호출/비교 구현은 하지 않음.
기반: 87738f2. branch feature/solar-extraction-tuning.
목표: profile-v13의 합성 근거 실패와 실제 외부 저장소 누락 개선.
공개 Profile/서비스 경계 유지. 최대3호출(추출2+수정1), 무재시도, 근거 엄격 검증.
고정 기준: 기존12종×2회+신규2건, 실제2문서×2회. 동일 정답/실패 포함/원문 비공개.
