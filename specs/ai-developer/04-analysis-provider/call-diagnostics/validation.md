# 호출 진단 검증 — 2026-09-25

## 완료 범위
core/features/repair 단계별 번호·필드·전송 크기·소요 시간·응답 크기·모델·토큰·오류를 기록한다.
최종 분석 결과 및 AnalysisError에 diagnostics를 추가했다. 원문·문서ID·키는 메타데이터에 포함하지 않는다.
프롬프트 profile-v18, 모델·샘플링·40초 timeout·최대3호출·무재시도·공개 Profile은 유지했다.
최종 실패에서 실패 응답만 옵션 저장. 수정으로 성공하면 실패했던 중간 응답도 저장하지 않는다.
미완료 응답에도 제공된 토큰 수를 기록한다. 토큰 정보가 없으면 null이며0으로 대체하지 않는다.
storage=failed는 진단 파일 저장 실패이며 분석 성공/기존 오류는 유지한다.

## 검증
- 전체 단위86/86 통과.
- Solar 합성6/6 통과, 총12호출, 모두 최초 성공. 진단 파일6개 저장 및 성공 원문0개 확인.
- 기술/기능 호출의 시간과 bytes/토큰 값이 실제 보고서에 기록됨.
- 만료정리 CLI 실행 성공, 이번 새 파일은 만료 전이어서 삭제0개.
- 단위: 단계2 timeout(재시도0), 검증수정 성공/실패, 실패응답 선택보관, 중첩 JSON에 숨은 키 생략, 파싱불가 응답 생략, 저장실패 영향차단, 동시분석 격리, TTL 경계/만료읽기/손상파일 정리/경로제한/중복쓰기 방어.
- 미완료 응답 토큰 누락 테스트의 실패를 확인한 후 수정. API·store 부재의 실패도 구현 전 확인.
- 코드 diff 직접 검토. 기존 추출 출력 형식·스키마 변경 없음.

## 보관 정책과 한계
파일에 created_at/expires_at(UTC,7일)을 저장하고 읽기·쓰기·purge 시 정리한다. 자체 UUID파일만 대상으로 비재귀 삭제하며 일반 파일은 보존한다.
로컬 프로세스가 중지된 동안에는 물리 삭제가 실행되지 않는다. 배포에서는 정기 purge 작업과 폴더 접근통제가 필요하다. OS 작업 스케줄러/서버 자동화는 이번 범위에 없음.
POSIX 신규 디렉터리0700/파일0600. Windows는 상위 폴더 ACL을 상속하며 별도 ACL 설정/암호화는 미구현이다.
timeout/HTTP오류처럼 응답 본문을 받지 못하면 원문이 없다. 과대·파싱불가·현재키/비밀패턴을 포함한 응답은 원문 보관에서 제외한다. 알려지지 않은 모든 종류의 비밀 탐지를 보장하지 않는다.
실패 기준은 분석 파이프라인 오류다. 구조검증을 통과했지만 평가정답과 다른 의미오류는 성공 분석이므로 원문을 저장하지 않는다. 평가 mismatch_fields로 따로 추적한다.
provider_elapsed_ms는 transport 전체 대기 시간이며 DNS/연결/모델생성 시간을 구분하지 않는다. 따라서 이번 기능만으로 기존 timeout의 원인을 확정하지 않는다.
추출 변경이 없어 기존 실제문서4건/합성24건 품질평가를 다시 돌리지 않았다. 기존 profile-v18 실제3/4(time out1) 결과는 그대로다.
기능 단위·중복 처리·새 문서 평가 확대는 후속 작업으로 남는다.

## 사용 (ai_service 디렉터리)
python -m agentfit_ai.evaluate --live --diagnostics-dir ../output/diagnostics --report ../output/new-evaluation.json
python -m agentfit_ai.name_stability --live --diagnostics-dir ../output/diagnostics --report ../output/new-stability.json
python -m agentfit_ai.diagnostics --directory ../output/diagnostics

라이브러리에서는 LocalDiagnosticsStore를 SolarAnalyzer의 diagnostics_store 인자로 전달한다. 생략하면 파일 쓰기 없이 반환 진단만 제공한다.
