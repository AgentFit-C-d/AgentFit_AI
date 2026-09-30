# 통합 분석기 런타임 검증

## 기준과 설치

- 기준 aacba7f, Windows Python3.13.3: 기존996건 중990통과·6제외,20.870초/exit0.
- 기존 기본 테스트 venv에서 실제 SDK 테스트 수집은 ModuleNotFoundError(langextract)/exit1. 이 브랜치에 새 `.venv`를 생성하고 requirements-dev만 설치한 경우에도 같은 실패를 확인했다.
- 같은 새 venv에 requirements-integrated를 설치했다. LangExtract1.7.0은 이 venv의 Lib/site-packages에 있고 include-system-site-packages=false다. 기존 평가 venv는 수정하지 않았다.
- 설치 후 `pip check`: No broken requirements found/exit0. 로컬 Python의 기존 prefix 경고는 있었으며 Linux 검증은 별도로 확인한다.

## 실제 SDK 통합 검사

실제 API0, 키 파일·개인 문서 읽기0. SDK나 extractor를 stub으로 대체하지 않았다. 실제 SDK4/4,skip0,0.071초/exit0.

1. 기본 통합 함수가 Solar 후보 추출부터 최종10필드 Profile을 반환한다. 요청5회와 원문 위치를 확인했다.
2. 동일 인용2개의 서로 다른 anchor 및 위치0..1/6..7을 유지했다.
3. 잘못된 JSON은 EXTRACTION_FAILED로 중단하고 후속 제공자 요청이 없었다. 오류 문자열과 trace에 합성 raw 응답이 포함되지 않았다.
4. 실제 SDK가 여러 청크를 처리할 때 max_calls1은 두 번째 전송 전에 CALL_BUDGET_EXCEEDED로 중단했다.

## 전체 회귀 검증

- 기존 평가용 기본 환경:996건/990통과6제외,20.325초/exit0.
- 새 선택형 환경:SDK4/4,0.050초 및 기존996건/991통과5제외,21.139초/exit0. 선택형 설치가 기존 `test_real_parser_keeps_anchor_without_example_alignment_warning`을 활성화해 제외가1개 줄었다. 나머지5개는 별도 Docling/reportlab 실험 의존성 부재로 제외됐다.
- 사용자가 공용 환경에1.7.0을 설치했다고 알렸으며 해당 환경을 수정하지 않았다. 위 평가용 venv와 사용자가 말한 공용 환경이 같은 경로라고 가정하지 않는다.
- `git diff --check` exit0. Windows의 기존 LF/CRLF 안내는 있었으며 알고리즘 제품 `.py` 변경은0개다.

## 남은 검증

독립 리뷰, 정확한 커밋의 Linux CI를 완료 후 기록한다. 이 기능은 패키지 설치와 실행 호환성 검증이며 H02 제공자 장애·의미 품질·서비스 연결을 해결했다고 주장하지 않는다.
