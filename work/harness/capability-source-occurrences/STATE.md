# 기능 인용 위치 확장 상태

- Goal active. 직전 제한 실험6요청/11호출은 exit0, 결과 cdde425를 feature/capability-candidate-recall에push. 현재 활성 모델 요청0.
- feature/capability-source-occurrences from cdde425, E:/AgentFit/tmp/worktrees/document-input-runtime 재사용. 기본 코드 수정 전 명세·계획 작성. 사용자 자율설계/직접구현 승인 유지.
- Task1 quote-only extractor → Task2 bool opt-in pipeline. 반복/부정/타제품 문맥별 위치·분류·근거를 유지한다. 기존동작/HTTP 기본변경0. 새코드 후 이전freeze는 새평가에 재사용하지 않는다.
- 로컬180초/suite, 실제평가는 최종review/CI후별도등록(3문서192호출/5400초 상한, 재시도0, 무료범위). 유료·개인문서추가전송·운영배포0.
- 다음: SDD커밋/전용ledger→Task1 RED→구현→GREEN→Task2. 의미 정확도·새문서일반화·사람수정부담·실제Spring/운영 gate는 미완료.
- Task1: 신규7테스트 구현부재 RED→인용 추출기 구현후7/7 GREEN. 전체unit1211건 중1205통과/Windows skip6,62.834초,session27760 exit0. 공용Python prefix 경고와 기존 CLI 잘못된 입력 테스트의usage 출력은 있으나 테스트실패0. 실제API호출0. 다음task1commit/task-done→Task2.
- Task1 bdb5204 complete/task-done7/7. Task2 unsupported-option RED8tests/12errors→옵션연결후GREEN8/8. 전체 최종unit1219중1213pass/6skip65.190초(session53612exit0),runtime35pass124.387초(session28355exit0),contract36pass6.504초,core8pass27.564초(session44155exit0). 합계1292pass/6skip. 새실제모델호출0. 다음Task2commit/task-done→독립최종review1회→필요시수정검증→push/CI→별도실제비교.
- Task2 f3ce59c complete/task-done8/8. 독립최종review1회 Critical0/Important1/Minor0: falsey callable이 기본전송으로 바뀌는 공통sender오류. 외부0 재현7assertion failures→None만기본선택/noncallable사전거절수정→9/9GREEN. 전체 재검증1294pass/6skip(unit1215pass6skip65.068초 session81444, runtime35pass123.916초 session15747, contract36pass6.696초, core8pass27.465초 session17270), 전부exit0. 리뷰 유보한 실제품질/일반화/운영은미검증유지. 새실제모델0. 다음최종commit/push/CI→새freeze/래퍼hash로3문서실제평가.
