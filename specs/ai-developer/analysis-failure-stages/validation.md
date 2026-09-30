# 분석 실패 단계 보존 검증

## 변경 범위

`feature/analysis-failure-stages`는 `ef6fad57104834f5e812044331e5dee939d87369`에서 분리했다. 제품 코드는 diagnostics의 고정 오류 코드 집합과 candidate_service_worker의 실패 변환만 수정한다. 추출·분류·검토 알고리즘, 모델, 프롬프트, 호출 예산, 평가 판정 기준은 변경하지 않는다.

## 재현과 회귀 테스트

2026-10-01 로컬에서 합성 실패를 주입했다. 실제 문서나 모델 API는 사용하지 않았다.

- 수정 전: 새 테스트 6개 실행, 하위 사례 포함 실패 22건. 안전한 단계 코드가 `ANALYSIS_FAILURE`로 사라지는 현상을 작업자·자식 프로세스·HTTP·평가 경계에서 재현했다.
- 수정 후: 같은 테스트 6/6 통과, 4.088초.
- 9개 단계 코드가 직렬화, 실제 자식 작업자와 부모 검증, FastAPI 응답, 실제 평가 점수 검증을 통과한다.
- 호출 예산 및 제공자 코드 우선순위 유지. 임의 문자열·null·list·dict·숫자·bool 단계는 안전한 일반 오류로 돌아간다. 원문·합성 키·상세 오류 표식이 출력되지 않는다.
- 실패 평가의 정답 분모 2개와 `status=failed`, 빈 산출 항목, `human_reviewed=false`, `release_gate_passed=false`를 유지한다.
- 기존 성공 응답 회귀는 전체 단위 테스트에 포함한다.

실행 위치는 새 작업 폴더의 `ai_service/`, 인터프리터는 기존 analysis-runtime의 프로젝트 전용 Python이다. 원래 작업 폴더의 코드를 가져오는 대신 현재 작업 폴더의 코드를 검증한다.

```text
python -m unittest discover -s tests -p test_pipeline_failure_stages.py -v
python -m unittest discover -s tests -v
python -m unittest discover -s runtime_tests -v
python -m unittest discover -s contract_tests -v
```

전체 로컬 검증은 통과했다.

| 검증 | 결과 | 시간 |
| --- | --- | --- |
| 단위·프로세스·HTTP | 1,123개 실행, 1,118 통과·5 건너뜀 | 64.374초 |
| 실제 SDK·로컬 TCP 통합 | 11/11 통과 | 51.350초 |
| Spring mock 계약 | 36/36 통과 | 11.468초 |

Python의 기존 `Could not find platform independent libraries <prefix>` 안내가 출력됐지만 각 검증의 종료 코드는 0이었다. 건너뛴 테스트를 통과로 계산하지 않는다. 최종 독립 검토·push 및 정확한 커밋의 CI는 별도 확인한다.

## 기존 평가 기준선

원래 analysis-runtime 작업 폴더에서 preflight가 통과했다. 공개 문서 10개, 임시 정답 207개, `release_gate_passed=false`이다.

- 정답 파일 SHA-256: `5fcdc3a15fdbd346e0e351313639c1ebe2cac02cc36f33abf749d2ff22caa283`
- 평가기 SHA-256: `8d6ab064551419943e18732dd5ba96763f8cbb1faeb029ec4470f6dd78f70f49`
- 기존 30회 계획 중 종료 결과는 실패 1건뿐이다. 중단된 다음 시도는 평가하지 않았으며, 이번 합성 테스트를 실제 모델 성공률로 합산하지 않는다.
- 이번 코드 변형을 기존 실행 디렉터리에 이어 쓰지 않는다. 향후 모델 평가는 별도 코드·조건 등록이 필요하다.

## 무료 사용 확인과 남은 검증

사용자가 개인 학습·연구용 무료 안내를 전달했다. [NVIDIA 공식 FAQ](https://docs.api.nvidia.com/nim/docs/product)는 개발자 프로그램의 무료 프로토타이핑 접근을 설명하며 실제 이용자에게 제공하는 활동도 운영 이용에 포함한다. [API 시험 약관 1.4절](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf)은 시험 한도와 크레딧 및 이후 별도 구독을 설명한다. 이 일반 안내만으로 현재 계정의 대상 모델·엔드포인트·잔여 무료 한도를 확인한 것은 아니다.

추가 요금이 없다는 계정별 확인 전에는 외부 모델 호출을 하지 않는다. 이번 작업의 외부 모델 호출은 0회이며 유료 전환·충전·대체·재시도도 없다. 키는 읽거나 출력하지 않았다. 모델 품질 개선, 과거 실패의 실제 원인, 실제 Spring 저장 및 운영 환경은 여전히 미검증이다.
