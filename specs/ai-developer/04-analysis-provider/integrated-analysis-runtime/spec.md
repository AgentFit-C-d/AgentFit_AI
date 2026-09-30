# 통합 분석기 선택형 런타임 설치

## 목적과 권한

실사용 목표의 설치 재현성 결함을 해소한다. 현재 통합 분석기는 LangExtract를 지연 import하지만 기본·개발 requirements와 CI에는 이 의존성이 없다. 사용자가 목표 내 설계·계획·구현을 자율 승인했고 SDD와 직접 구현을 요청했다. 이번 작업은 기존 흐름의 제한된 설치·검증 보완이며 공개 API 변경은 없다.

## 선택

`ai_service/requirements-integrated.txt`가 기존 requirements와 `langextract==1.7.0`을 포함한다. 이 버전은 실제 평가 환경의 설치 metadata로 확인했다. 기본 환경의 경량 설치와 선택형 분석 환경을 구분할 수 있다. 기본 requirements에 일괄 추가하거나 개발자 수동 설치에 의존하는 안은 채택하지 않는다. LangExtract의 추가 Provider extras는 설치하지 않으며 기존 Solar 사용자 모델 어댑터를 쓴다.

## 요구사항

1. Python 3.13의 깨끗한 가상환경에서 선택형 requirements와 기존 테스트 의존성을 설치하고 `pip check`가 통과해야 한다. 다른 로컬 venv의 패키지나 환경 키에 의존하지 않는다.
2. 실제 설치된 LangExtract의 모델 어댑터·JSON 해석·위치 정렬을 실행한다. `extractor`나 `lx.extract`를 대체하지 않고 외부 HTTP 전송 경계만 합성 응답으로 대체해 기본 `analyze_integrated_candidates`가 10개 필드 Profile을 반환하는지 검증한다. 실제 API 호출은 0이다.
3. 반복 인용의 서로 다른 anchor와 원문 위치가 보존되는지 검증한다. 파싱 불가능한 제공자 응답은 EXTRACTION_FAILED 단계로 안전하게 실패하고 후속 제공자는 호출하지 않는다. 호출 예산1이 실제 SDK의 여러 청크 추출에서도 두 번째 전송 전에 강제돼야 한다.
4. 선택형 테스트는 `ai_service/runtime_tests/`에 둔다. 기본 테스트 검색은 기존 `tests/`만 대상으로 한다. 선택형 테스트는 LangExtract를 실제 import하므로 누락 시 실패하며 skip으로 설치 실패를 숨기지 않는다.
5. 기존 Linux CI와 별도의 `integrated-runtime` job에서 선택형 설치·pip check·실제 SDK 테스트·전체 기본 테스트를 실행한다. Ubuntu24.04/Python3.13, job 상한15분을 사용한다.
6. 한국어 설치 및 오프라인 검증 명령을 통합 분석 README에 기록한다. HTTP 기본 분석기 연결, 실제 모델 품질, Spring 저장 및 배포 완료와 이번 검증을 구분한다.

## 경계와 인수 근거

- 공개 Profile·기본 HTTP·모델·프롬프트·64호출 상한·재시도 정책을 변경하지 않는다.
- 직접 의존성 버전을 고정하며 전이 의존성의 완전 lock을 주장하지 않는다. `pip check`와 실제 CI로 현재 조합 호환성을 검사한다.
- 기존 테스트 환경에서 SDK import 실패를 RED로 기록하고, 새 환경 설치 후 실제 SDK4건 및 전체 테스트·정확한 커밋의 Linux CI를 인수 근거로 남긴다. SDK 테스트가 기존 설치 환경에서 먼저 통과하는 것은 기존 알고리즘의 특성 확인이며 새 알고리즘 구현으로 주장하지 않는다.
- 기본 branch base aacba7ff348e929aaa1a9a4b8300b40be1099527. 직전 H02는 최종 결과 없이 제공자 오류로 종료했으며 모델 품질 개선은 미입증이다.
