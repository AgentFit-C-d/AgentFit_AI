# 통합 분석 진입점의 기존 민감값 검사 적용

## 목적과 관찰

통합 후보 분석을 서비스에 연결하기 전에 기존 Solar와 동일한 입력 차단 경계를 적용한다. 오프라인 합성 재현에서 `password=` 뒤의 충분히 긴 가짜 값은 `_reject_sensitive`가 거절했지만 `analyze_integrated_candidates`에서는 추출 callback까지 도달했다. 현재 함수는 전달받은 API key의 직접 포함만 검사한다.

실제 평가 중인 source-name-expressions checkout은 고정한다. 별도의 `feature/integrated-input-guard` checkout에서 변경한다. 사용자 목표의 자율 설계·계획·직접 구현 승인에 따라 진행한다.

## 계약

- `analyze_integrated_candidates`의 기존 입력·옵션 검사가 끝난 뒤, extractor·transport·observer 실행 및 trace 변경 전에 document와 document_id에 기존 Solar `_reject_sensitive`를 적용한다.
- 새로운 정규식이나 자동 삭제는 추가하지 않는다. 기존 정책이 탐지하는 private key 표식, 충분히 긴 명시적 자격정보 대입, 정해진 key/token 형식을 같은 기준으로 거절한다. 탐지 대상의 전수 보장을 주장하지 않는다.
- 차단 결과는 본문 없는 `AnalysisError('SENSITIVE_CONTENT')`다. 원문·검출 위치·키·후보를 예외/로그/trace에 넣지 않는다.
- 기존 직접 API key 포함 거절과 잘못된 입력·옵션의 ValueError 동작은 유지한다. 전달받은 Solar/NVIDIA key 모두의 직접 포함 검사는 기존 검사가 담당한다.
- 주입 extractor와 기본 LangExtract 경로 모두 외부 동작 전에 동일하게 차단한다. 차단된 입력에서 extractor·Solar·NVIDIA·observer 호출은 0이고 기존 collector 내용은 바뀌지 않는다.
- 민감값 패턴이 없는 정상 문서는 모델·프롬프트·재시도·64회 예산·대표 기능 최대30개·Profile 계약이 그대로 유지된다. 기본 HTTP 서비스와 보관 정책을 변경하지 않는다.

## 검증과 한계

가짜 값만 사용한 문서/ID 차단, 기본·주입 추출 경계 호출0, 기존 collector 보존, 정상 전체 파이프라인 동일 결과를 RED→GREEN으로 확인한다. 기존 전체 suite와 Linux CI를 통과시키고 독립 리뷰 후 push한다. 실제 API를 호출할 필요는 없으며, 이 검증은 모델 의미 품질이나 전체 서비스 완료의 증거가 아니다.

## 자체 검토

기존 정책 재사용이므로 Solar와 통합 모드의 기준이 갈라지지 않는다. 직접 key 포함 검사는 앞선 기존 계약을 유지한다. 거절을 extractor 호출 후에 수행하거나 실패 trace로 기록하지 않는다. 장시간 평가의 제품 해시는 이 별도 checkout 변경의 영향을 받지 않는다.
