# E1·E2 오프라인 실행 기록

- 승인 범위: 원문 위치 registry 및 저장 응답 감사. S1–S3, 모델 호출, 서비스 연결 제외.
- 시작: 2026-10-01 11:40:58 UTC. 종료 상한: 13:40:58 UTC (2시간).
- 기준 커밋: 6cf018e. 브랜치: feature/candidate-evidence-audit.
- 기존 dirty 파일은 그대로 보존하고 커밋에서 제외한다.
- 큰 goal은 paused 유지. 이번 작업의 완료 여부와 별개다.

## 실행 순서

- [x] E1: 실패 회귀 → 원문 registry/참조 해석 → 통과 확인
- [x] E2: 저장 원자료 해시 확인 → 실패 회귀 → 감사 → A68/B68, 결함12/22 재현
- [x] 전체 로컬 회귀 및 최종 독립 검토, 결과 문서
- [x] 구현 커밋·push (ed6c98b, 종료 문서 후속 기록)

## 구현 결정

- Windows 환경에서 bash 전용 SDD 작업 스크립트 대신 이 파일에 작업 시작·완료·검증을 기록한다.
- 크기 상한 초과 시 원문과 frozen 입력 전체를 보존하고 complete=false로 반환한다.
- 잘못된 참조·hash·범위는 계약 오류이며 부분 성공으로 바꾸지 않는다.
- unit 선택 결과는 위치/문맥 정보만 제공한다. 의미 판단이나 기존 판정 수정은 하지 않는다.
- E2에 로컬 파일 replay를 포함해 저장 원자료·응답을 바이트 단위로 보존·검증한다.
- 이 실행에서 평가 기준과 기존 audit.json은 수정하지 않는다.

## 검증 로그

- E1 RED: 10개 테스트 실행, 계약 미구현으로 실패 확인(잘못된 범위 미거절 등).
- E1 GREEN: 동일 10개 모두 통과. 실행 0.007초. 기존 판정을 출력하는 함수 없음.
- E1 원문 registry의 원문/frozen 사본 보존, 정확 위치, 전체 다중 줄 coverage,
  반복/표/원격 부정/Unicode/CRLF/해시 변조/상한/선택 참조 회귀 완료.
- Task E1 complete: 6cf018e..3533cfd, 위 10개 테스트 통과 후 커밋.
- E2 RED: 저장 응답 회귀에서 감사 미구현 실패, fixture 20개 원본 바이트 해시는 통과.
- 회귀 작성 중 Firefox 기대 사례의 후보 번호 C016을 잘못 적었다. 저장 원응답 대조 후 실제
  Firefox C013으로 수정했다. 정답·원응답·평가 기준 변경 없음.
- E2 GREEN: 저장 원응답 및 파일 보존/계약 검증 16개 통과(1.302초).
- 실데이터 오프라인 CLI 실행: A68/B68, quote_not_found=2/4, exact_elsewhere=10/18,
  총 인용 결함=12/22. 기존 record 변경0, raw row 유실0, 새 모델 호출0, 서비스 적용false.
- 결과: E:/AgentFit/output/evidence-source-audit-v1/audit.json.
- 원자료22개를 별도 originals/에 바이트 단위 복사하고 읽기 전후/복사본 일치를 확인했다.
  원자료는 기존 output/direct-field-comparison-v1에 그대로 남는다. CLI 감사 시간0.321초.
- portable fixture는 inputs/summary/18응답을 원형 보존한다. 중복 요청 프롬프트인
  freeze/payloads는 fixture만 제외하고 실제 replay에서는 함께 검증·보존한다.
- 완전한 문맥이 없는 상한 초과는 incomplete_context가 우선한다. 그 안의 인용 결함은
  issues에 함께 남긴다. 완전한 입력에서는 quote_not_found→exact_elsewhere 순으로 집계한다.
- Task E2 complete: 3533cfd..ed6c98b, 위 16개 테스트 및 실데이터 CLI 집계 통과 후 커밋.
- 전체 단위 회귀: 1329개 실행, 1322 통과/7 skip, 실패0, 91.600초.
  명령: ai_service에서 `rtk proxy <venv-python> -m unittest discover -s tests -q`.
  원본 로그: E:/AgentFit/output/evidence-source-audit-v1/unit-tests.log.
- 최종 독립 검토: 6cf018e..ed6c98b에 Critical/Important/Minor 지적0.
  검토자가 원본22개/복사본 및 portable fixture20개를 해시·바이트 대조하고
  감사 결과를 메모리에서 재계산해 A68/B68, 결함12/22 및 공통 출력 전체 일치를 확인했다.
- 판단 제외 항목에 대한 결정: S1–S3 의미 판단, 실제 모델 일반화/정확도, 서비스 통합/배포는
  사용자 보류 범위이므로 그대로 미검증으로 남긴다. 이 작업을 그 영역의 개선/완료로 해석하면 안 된다.
- 최종 차이 확인: 서비스 모듈·기존 A/B 비교 코드·고정 audit.json·관계 계획 diff0.
- 구현 ed6c98b까지 origin/feature/candidate-evidence-audit push 성공 확인.
- 로컬 구현·검증 종료 확인: 2026-10-01 12:05:25 UTC, 시작부터 약25분(2시간 이내).
- 큰 goal paused, 새 모델 호출0, S1–S3/B 반복/서비스/배포 미실행을 유지한다.
- 이번 요청의 남은 구현 없음. 종료 문서도 같은 브랜치에 기록하며 기존 dirty와 결과 파일을 보존한다.
