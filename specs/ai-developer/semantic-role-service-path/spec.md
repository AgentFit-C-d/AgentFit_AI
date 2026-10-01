# 의미 역할 검증의 서비스 경로 연결

## 요청과 범위

`/internal/v1/analyze`부터 최종 응답까지 의미 역할 검증과 불확실 후보 보존을 연결한다. 기존 API 계약은 유지한다. 운영 배포·실제 Spring 수정·Luna 실험은 제외한다. 기존 큰 goal은 paused이며 이 한정 작업 종료 후 자동 재개하지 않는다.

## 관측과 설계

- `create_app`은 프로세스 환경의 `AGENTFIT_ANALYSIS_MODE`를 읽는다. 생략 시 default/Solar다. `.env` 자동 로딩 없음.
- `integrated-nvidia` HTTP → run_analysis_process → analysis_worker.execute_request → execute_nvidia_analysis → analyze_nvidia_candidates.
- 현재 worker가 semantic_assessment를 전달하지 않아 False가 적용된다. 기존 선택형 개선을 서비스에서 쓰지 못한다.
- **수정:** NVIDIA 서비스 worker 경계에서 semantic_assessment=True를 명시한다. 기존 v2 응답 검증·선택적 modelDecisions/unassignedQuestions 전달을 재사용한다. HTTP 옵션으로 우회/강등시키지 않는다.
- Solar/v1와 혼합 모드는 임의로 변경하지 않는다. NVIDIA 모드를 고르지 않은 환경은 적용되지 않는다는 사실과 필요한 실행 설정을 보고한다. 배포 서버 설정은 확인 자료 없이는 추정하지 않는다.
- first classification→review→curation→projection→worker validation→HTTP에서 후보 ID/근거/판단/질문을 대조한다. 불명확 후보는 final needs_confirmation의 metadata와 질문에 남아야 한다. 명백한 비제품 설명 제외와 실제 유실은 구분한다.

## 완료 기준

1. 실제 환경에서 확인 가능한 비밀 아닌 설정과 저장소 실행 지침을 구분해 기록.
2. 외부 API 없는 실제 SDK·자식 프로세스·HTTP 회귀에서 정상 제안과 불확실 후보가 함께 남고 v2 계약 유지.
3. 이름/순서 변형 기존 회귀와 개발에 사용하지 않은 공개 문서를 분석 입력부터 최종 출력까지 비교. 같은 문서·사전 고정 정답으로 오확정·정상 누락·확인 필요·시간을 보고한다. 모호한 정답과 평가 범위 밖 출력도 별도 표시한다.
4. 실제 모델 평가는 무료 계정 확인이 유효할 때만 실행. 고정 응답 시험과 실제 모델 시험 분리. 호출 불가/한도 거절 시 유료 대체 없이 로컬 결과만 보고.
5. 수정 전 결과·코드·입력·정답을 보존하고 feature 브랜치 push. 이번 작업 결과와 미검증 부분을 보고하고 종료.

## 해석 제한

신규 공개 문서는 개발용 정답 수정을 위한 반복 튜닝에 사용하지 않는다. 정답은 호출 전에 작성한 임시 사람 검토 미완료 기준이며 명시적 주장만 정상/오류 기준으로 삼는다. 셀프호스팅·에디션 등 애매한 사항은 사람 검토 대상으로 분리한다. 모델 사전학습 노출은 알 수 없다. 전체 응답 outcome=needs_confirmation과 각 후보의 의미 보류 수를 혼동하지 않는다.
