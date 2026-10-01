# 구현·검증 계획

1. 경로/환경 조사: 모드·기한·키 존재 여부만 읽고 키 값은 출력하지 않는다. deploy manifest 및 로컬 실행 프로세스 존재를 확인하되 원격 배포는 미확인으로 남긴다. 기준 커밋 5de4020 보존.
2. 고정 응답 RED: 실제 HTTP/worker 경로의 모델 fixture가 정상 서비스·기능과 용도/역할 미정 후보를 반환하게 한다. modelDecisions/원문/질문 보존과 정상 정보 유지 assertion이 기존 경로에서 실패해야 한다.
3. 최소 GREEN: analysis_worker의 integrated-nvidia 경로에 semantic_assessment=True를 전달. 기존 runtime fixture를 새 내부 응답 계약에 맞춘다. API schema·응답 필수키·프로세스 보안/취소/실패 계약 유지.
4. 문서 평가 준비: 원래 Documenso 전체 README와 신규 공식 공개 README를 고정한다. 기존 이름/문장순서 회귀 입력은 로컬 통합 평가에 포함한다. 사전 정답·모호 항목·출력 대조 방식·코드 해시를 동결한다.
5. 실제 비교: 동일 DeepSeek 추출/분류/정리+GLM 검토, 변경 전/후 각1회. 문서2개 × 2경로=4요청, 요청당 최대64호출/1800초, 전체256호출/최대2시간, 재시도0. 현재 무료 확인의 두 모델/endpoint/만료를 매 호출 검사, 오류/무료 제한 거절 시 전체 중단. 추가 튜닝/모델 변경/유료/Luna 없음. 공개 문서만 전송.
6. 전체unit/contract 및 영향받는runtime/core-flow, 독립 코드 리뷰1회, 결과 보고·feature commit/push·CI 확인 후 종료.

검토 중점: worker 옵션 누락/다른 모드 영향, 중간 후보 유실, 모델 confirmed와 사용자승인 혼동, 구형 v2 기록 호환, 실제/고정 평가 구분과 비용 게이트. 사용자의 명시적 연결·검증 지시에 따라 직접 순서대로 진행하며 기존 설계를 다시 승인받지 않는다.
