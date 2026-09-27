# 구현 계획 — 확인 대기

1. 기존 section 보존 위에 anchor ID 및 정확 인용 해석기 추가. 먼저 회귀 테스트.
2. 후보 생성 schema에서 분류 라벨 제거. source quote와 unit ID만 허용.
3. Solar 후보 판단 schema/validator와 Profile 변환 연결. Jev 사용하지 않음.
4. 최대6회·60초·실패 원본7일·기본경로 유지 확인.
5. 사전 고정 최종 Profile 의미 골드와 기존 exact 점수를 함께 기록하는 합성 비교.
6. 3회 통과 시 기존 실제 튜닝 문서로 확대. 공개 검증 문서는 최종 설정 고정 전 미사용.
7. 결과와 한계, 검증 결과를 기능 브랜치에 commit/push.
