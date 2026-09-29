# 후보 탈락 사유 계약

## 목적·근거

실사용 분석에서 명시된 제품 사실을 검토가 잘못 버리는 문제를 줄인다. H02 동작 후보 실험에서 명시적 인증 API 후보가 탈락했다. 동일 문제 묶음의 원래 요청 재생은 같은 탈락을 보였고, 탈락 사유 코드를 추가한 진단 요청은 이를 보존했다. 아직 단일 묶음 결과이며 일반 개선이라고 판단하지 않는다.

기존 구조는 잘못된 후보 ID만 받고 이유를 구별하지 못한다. 이름별 예외나 검토 생략은 선택하지 않는다. 기존 모델·후보·필드 정의·최종 변환을 고정하고 **탈락 ID마다 하나의 사유를 요구하는 선택형 내부 계약**만 추가한다. 사용자 목표의 설계·계획·구현 자율 진행 승인을 적용한다.

## 계약

- `review_candidates_separately(..., reasoned_review=False, review_reasons=None)`를 추가한다. False일 때 기존 API 요청·반환값은 동일하다.
- True일 때 후보 묶음 응답은 기존 checkedCandidateIds, wrongCandidateIds와 rejectionReasons를 갖는다. 각 사유는 정확히 `{id, reason}`이며 wrongCandidateIds와 일대일 대응해야 한다. 순서는 자유다.
- reason은 wrong_field / not_current / not_product_fact / insufficient_evidence 네 값이다. 정확한 원문 인용, 자유 설명, 수정 값을 반환하지 않는다. 코드도 의미 정확성의 증명으로 간주하지 않는다.
- checkedCandidateIds는 입력 순서와 같고, wrongCandidateIds는 현재 묶음의 중복 없는 부분집합이어야 한다. 사유 누락·중복·잘못된 ID/타입/enum·추가 키는 전체 묶음 실패다. 실패한 결과로 커버리지나 Profile을 만들지 않는다.
- review_reasons는 선택적 list 수집기다. 검증된 사유만 batch_index, sub_batch_index, id, reason으로 복사한다. 키·원문·값·응답 전문은 넣지 않는다. 앞선 성공 묶음 기록은 뒤 묶음 실패 시에도 남는다.
- 기존 모델/finish_reason 검증, Solar 토큰 상한 시에만 하위 묶음 재검토, 전체 원문 커버리지, wrongCandidateIds 최종 처리 규칙을 유지한다. 사유가 붙었다고 잘못된 후보를 다시 살리거나 자동 완료 기준을 완화하지 않는다.
- 호출 수 증가 없음: 기존 최대20개 후보 묶음 및 마지막 커버리지1회. 기본 HTTP 분석기·공개 Profile·서비스 호출 예산 변경 없음.

## 검증·적용 기준

응답 계약·원문 위치 유지·다중 묶음·실패 후 부분 결과 금지·기본 요청 불변을 테스트한다. H02의 병합183개 후보와 분류를 고정해 DeepSeek 전체 검토를 기존/사유 모드로 비교한다. 지정6개 검사는 부가 지표다. 명시적 인증 API 유지와 미래/부정 제외, 기능 기대효과 오확정을 함께 관찰한다. 후보 수나 검사 통과만으로 승격하지 않으며, 반복 안정성·다른 문서 및 서비스 연동은 후속 게이트다.
