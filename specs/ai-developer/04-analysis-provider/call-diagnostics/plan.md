# 계획
1. 호출별 trace를 analyze 지역변수로 유지해 평가의 동시 호출 간 섞임 방지.
2. transport 경계 계측 및 단계별 검증 결과를 추적. 원문은 지역 메모리로만 전달하고 반환 진단에서 제외.
3. LocalDiagnosticsStore: UUID 파일, 독점 생성, POSIX0600(Windows는 상위 폴더 ACL 상속), UTC expires_at, 보관 폴더의 자체 파일만 비재귀 purge.
4. 평가 CLI와 결과 JSON에 진단을 연결. --diagnostics-dir로 명시적 로컬 보관. 별도 purge CLI 제공.
5. TDD: 단계2 timeout, 수정성공/실패, 성공원문 미보관, 민감응답 생략, TTL 경계/다른파일보존, 저장실패, 동시분석 분리.
6. 전체 단위검증 + 소수 합성 실호출로 진단 연결 확인. 추출 변경이 없어 전체 품질평가는 반복하지 않는다.
7. 검토/결과기록/비밀검사/기능브랜치 push.
