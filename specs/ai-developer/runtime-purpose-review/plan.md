# 제품 용도 규칙 비교 계획

**분류:** 제한 조사(spike), 직접 실행. 자율 설계·진행 승인 유지.

**Spec:** [spec.md](spec.md)

- [x] 공통 prompt.txt와 합성 입력·기대 ID 사전 고정. 특정 제품이나 gold의 정답을 지침에 넣지 않았다.
- [x] 검증된 replay helper와 별도 adapter 사용. 기존 출력·서비스 코드 변경0.
- [x] 외부0 adapter 검증3/3. v2 혼합 필드 variant도3/3.
- [x] v1 6요청22호출 exit0. 부작용 후 plan-v2.md를 먼저 등록하고 v2 6요청22호출 exit0. 재시도/요청실패0.
- [x] result-v1.md/result-v2.md, audit.json/audit-v2.json 기록 및 commit/push 단계. 두 버전 모두 기본 적용 보류.

최종 산출물은 근거 있는 채택/보류 판단이다. 제품 코드 변경 및 기본 적용은 이 제한 조사에 포함하지 않는다.
