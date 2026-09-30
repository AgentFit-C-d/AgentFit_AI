# NVIDIA 단독 내부 분석 검증

## 구현

- 전용 진입점 `agentfit_ai.candidate_analysis_pipeline.analyze_nvidia_candidates`: NVIDIA 키 하나, 후보 추출/분류 모델 선택, 기존 검토·기능 정리 모델 유지.
- DeepSeek V4.1 Flash / GLM5.3 / Kimi K3의 기존 allowlist만 허용. 반환 model은 선택 model과 일치해야 한다. 실제 NVIDIA adapter를 재사용하며 Solar 응답으로 위장하지 않는다.
- 공동64호출 상한·자동재시도0, 첫 transport 실패 이후 추가 전송 금지. SDK가 오류를 삼켜도 해당 단계 실패를 반환한다.
- HTTP/작업자 설정·독립 평가 runner는 이번 변경에 연결하지 않았다. 새 내부 경로를 기존 혼합 baseline으로 기록하면 안 된다.

## 로컬 증거

- 기준선: 기존 pipeline20/20.
- RED: unit5개(하위 실패9/미지원 옵션 오류9), runtime4개(테스트 subTest 범위 보정 후 기능 부재 실패6/옵션 부재1). 외부 연결 없음.
- GREEN: 신규unit5/5, 신규runtime4/4. 실제 설치된 LangExtract1.7.0과 기존 parser/근거/분류/검토/v2를 실행하고 provider 생성만 합성 응답으로 대체.
- 첫 전체 gate: unit1128건 중1123통과/5skip59.946초, runtime15/15 47.452초, contract36/36 9.369초, core-flow4/4 21.882초. task-done 최종 결과는 아래 기록을 따른다.
- 기존 Python의 `<prefix>` 경고가 출력되지만 신규 테스트와 위 검증은 exit0. 기존 Windows 비지원 조건의 skip을 성공으로 집계하지 않는다.

## 실행 방법과 잔여 검증

워크트리의 `ai_service`에서 통합 의존성이 있는 Python으로:

```text
python -m unittest discover -s tests -p test_nvidia_only_candidates.py
python -m unittest discover -s runtime_tests -p test_nvidia_only_runtime.py
```

테스트는 합성 키/응답만 사용하며 실제 `.env`를 읽지 않는다. 실제 호출 예산0. 이 함수는 과금 여부를 조회하지 않으며 전체 요청 wall timeout은 상위 worker/runner가 책임져야 한다. 실험 재개 전 계정별 무료 대상·한도 확인, 별도 실행 manifest/출력 경로, process deadline 연결이 필요하다. 기본 FastAPI는 여전히 기존 혼합 경로다.

정확도 개선·실제 endpoint의 schema 지원·현재 계정 과금/잔여 한도·실제 Spring/운영 배포는 검증하지 않았다. 공식 무료 prototyping 안내는 계정 증빙을 대신하지 않는다.
