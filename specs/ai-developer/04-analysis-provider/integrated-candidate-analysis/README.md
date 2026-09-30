# 전체 후보 분석 통합

`agentfit_ai.candidate_analysis_pipeline.analyze_integrated_candidates`는 문서 원문부터 최종 후보 Profile까지 실행하는 선택형 내부 함수다.

## 선택형 런타임 설치

기본 HTTP 서비스의 설치 파일과 통합 분석기 설치 파일을 구분한다. Python3.13의 별도 가상환경을 활성화한 뒤 저장소 루트에서 실행한다.

```text
python -m pip install -r ai_service/requirements-integrated.txt
python -m pip check
```

이 파일은 기존 서비스 의존성과 LangExtract1.7.0을 설치한다. 추가 Provider extras는 사용하지 않으며, 일반 후보 생성은 기존 Solar 어댑터가 담당한다. 전이 의존성 전체를 고정한 lock 파일은 아니다.

오프라인 검증은 테스트 의존성을 추가 설치한 뒤 실행한다. 실제 API 키나 `.env`가 필요하지 않다.

```text
python -m pip install -r ai_service/requirements-dev.txt
cd ai_service
python -m unittest discover -s runtime_tests -v
python -m unittest discover -s tests -q
```

`runtime_tests`는 실제 LangExtract를 실행하며 외부 전송만 합성 응답으로 대체한다. 설치 누락은 import 오류로 실패한다. 기본 `tests`와 분리돼 있으므로 기본 서비스 환경에서 LangExtract 없이 기존 테스트를 실행할 수 있다. CI의 별도 `integrated-runtime` job은 깨끗한 Ubuntu24.04/Python3.13에서 두 묶음을 모두 검사한다.

검증 범위는 기본 추출 경로→최종 Profile, 반복 인용의 anchor·위치, 잘못된 응답의 안전한 중단, 여러 청크의 공통 호출 예산이다. 실제 모델의 정확도나 제공자 가용성, HTTP 연결·Spring 저장·배포 완료를 입증하는 검사는 아니다. [명세와 설치 검증 기록](../integrated-analysis-runtime/validation.md)을 참고한다.

## 실행 흐름

1. Solar LangExtract로 일반 후보를 추출하고 정확한 원문 등장 위치를 확장한다.
2. DeepSeek로 동작 후보를 추가 추출한다.
3. 같은 원문 위치를 합친 후 Solar로 전체 후보를 한 번 분류한다(요청당 최대 30개).
4. GLM으로 확정 후보를 20개씩 검토하고 전체 원문 누락을 확인한다.
5. 반려 후보를 제외하고 확정 기능의 고유 값이 30개를 넘으면 DeepSeek로 대표 구성·관계 검토·최대 한 번 복구한다.
6. 기존 Profile 검증과 확인 필요 판정을 적용한다.

`review_model`, `feature_model`은 기존 NVIDIA 세 모델 중 선택할 수 있다. Solar 키는 일반 추출·분류에만, NVIDIA 키는 동작 추출·검토·대표 구성에만 전달한다. 확정 판단에는 `explicit-v1` 필드 정의를 사용한다.

## 호출 및 오류

- 원문 최대 100,000자, 합친 후보 최대 240개, 대표 기능 최대 30개다. 초과 후보를 잘라서 성공시키지 않는다.
- 추출·전송·관측 콜백 전에 문서와 문서 ID에 기존 Solar 민감값 검사를 적용한다. 기존 정책이 탐지하는 자격정보 패턴은 원문 없는 `AnalysisError('SENSITIVE_CONTENT')`로 거절하며 trace를 추가하지 않는다. 두 Provider key의 직접 포함과 잘못된 입력·옵션의 기존 거절도 유지한다. 이 패턴 검사가 모든 형태의 비밀을 탐지하는 것은 아니다.
- `max_calls`는 두 제공자의 합산 요청 상한이다. 기본 64, 허용 범위 1~64이며 다음 전송 전에 차단한다. 각 기존 요청은 600초·출력 8,192토큰을 사용한다. 전체 처리시간 보장은 없다.
- 기본 LangExtract 추출의 모든 전송도 계측한다. 사용자가 직접 주입한 `extractor` 내부의 별도 네트워크 호출은 이 계측 범위 밖이다.
- 호출 상한은 `CandidatePipelineError.detail == 'CALL_BUDGET_EXCEEDED'`, 다른 오류는 고정 단계와 허용된 오류 코드로 전달한다. 공급자 예외 본문은 반환하지 않는다.
- `call_trace`는 단계, 제공자, 요청 모델, 실제 시도 순번, 시간, 응답 바이트 수, 전송 완료 여부와 `attempt`, `retry_of_call_index`, `provider_error`를 담는다. 전송 완료는 유효 JSON·의미 검증 성공을 뜻하지 않는다.
- 기본 NVIDIA 전송은 SSE 스트리밍이다. 종료 이벤트와 모델 일치를 확인한 완성 응답만 기존 JSON·스키마 검증으로 넘긴다. 명시적으로 주입한 전송 함수는 우선 적용한다.
- NVIDIA 요청은 자식 프로세스에서 실행하고 부모가 각 시도 전체의 기한을 적용한다. 전송 데이터는 최대 16MiB, 이벤트와 완성 응답은 각각 최대 1MiB다. 스트리밍의 `response_bytes`는 전송된 전체 SSE 크기가 아닌 정규화한 완성 응답의 크기다.
- 통합 함수의 `nvidia_retry_limit`은 기본 1이며 0으로 끌 수 있다. NVIDIA `PROVIDER_UNAVAILABLE`만 첫 실패 후 2초 대기하고 동일 요청을 한 번 다시 보낸다. 앞 단계는 반복하지 않는다. Solar·다른 전송 오류·모델 출력 및 의미 실패에는 적용하지 않는다. 모든 실제 시도는 같은 64회 상한에 포함하며 예산이 없으면 대기·전송하지 않는다.
- 최초 실패 행은 유지하고 재시도 행이 해당 `call_index`를 참조한다. 전송 복구 횟수와 최종 분석 성공을 따로 평가해야 한다. 재시도는 추가 시간·호출 비용을 사용하며 지속적인 제공자 장애를 해결한다고 보장하지 않는다.
- `observer`는 합쳐진 `grounded`, `classified`, 검토 후 `reviewed`, 최종 `projected`의 복사본을 받는다. 원문에서 나온 값이 포함될 수 있으므로 무단 출력·저장하지 않는다. 콜백 실패는 분석 실패로 처리한다.

## 결과 판정

`candidate_profile` 또는 `needs_confirmation`을 반환한다. 후보 반려·잘못된 확정·원문 누락·대표에 포함되지 못한 기능은 기존 확인 필요 판정을 유지한다. 대표 선택 전의 검토 기록과 최종 표시할 대표 목록을 구분한다.

기본 HTTP 경로는 아직 이 함수를 호출하지 않는다. 전체 경로의 실제 문서 품질, 독립 문서 평가, Spring·프론트 확인 및 저장 연동을 검증한 뒤 서비스 적용을 판단한다. 단위 테스트나 일부 정답 항목 통과만으로 실사용 완료를 판정하지 않는다.
