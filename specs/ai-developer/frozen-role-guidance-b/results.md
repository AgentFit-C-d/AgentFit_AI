# 동결 B 지침 통합 — 오프라인 결과

## 변경 범위와 적용 경로

- 브랜치: `feature/frozen-role-guidance-b`, 시작 코드: `716031e`.
- 선행 수정 모두 포함: tentative/proposed 보류 `10b8d02`, v3 검토 보존 `e5ec802`,
  따옴표 위치 연결 `e73a43a`. 해당 제품 파일에 기존 미커밋 변경이 없었다.
- 제품 변경은 `ai_service/agentfit_ai/candidate_mention_roles.py`의
  `MENTION_ROLE_INSTRUCTION` 문자열 하나다. 동결 B와 바이트 수준으로 같다.
- B SHA256: `f6c4265d4f459babee04e5ed010b9ac81525dcbe3c77ba784ebd54dbb0229523`.
- 실제 integrated-nvidia 요청은 `analysis_worker.execute_request`에서
  `execute_nvidia_analysis(semantic_assessment=True)`를 거쳐
  `classify_grounded_candidates` → `assessment_payload` → NVIDIA 전송기로 흐른다.
  이 분류 전송 경계에서 생성한 요청 전체를 저장 B 요청과 비교했다.
  원문·후보·앞뒤 문맥·다른 지침·스키마·모델·출력/추론 옵션이 모두 동일하다.
- 서버 판단, 프롬프트 내 다른 블록, 모델 선택/옵션, 스키마, 계약, 검토,
  위치 연결, Spring, 속도 관련 코드는 변경하지 않았다.

## 저장 B 응답 재생

짧은 합성 문맥 D1/D2의 기존 실제 B 응답을 오프라인 재판정했다.
새 모델 요청이나 실제 문서 전체 재평가는 아니다.

| 문서 | 정상 supported | excluded | needs_confirmation |
|---|---:|---:|---:|
| D1 | 5 | 3 | 0 |
| D2 | 4 | 2 | 2 |
| 합계 | **9** | **5** | **2** |

- 두 대상의 이름·유형·도메인6개와 정상 인증/SDK 연동3개가 supported로 유지됐다.
- 예시의 다른 프로젝트2개, 호환/설정 지원 대상2개, 명시 부정1개가 긍정 값으로 통과하지 않았다.
- RelayWave tentative/proposed와 VaultMesh 상충 근거 후보는 needs_confirmation이다.
  보류2개를 모델 정확도 향상이나 사용자 확정으로 계산하지 않았다.
- 원시 `confirmed` 오류4개(other/confirmed2, 예시 프로젝트 confirmed1,
  부정 문맥 confirmed1)는 그대로 남고 서버에서 제외된다.
  원시 field·mentionKind·modelStatus·의미 축·support·counterEvidence는 덮어쓰지 않았다.
- v2/v3 확인 응답 경계에서 보류2개의 sourceValue·위치·원시 판단·반대 근거와 질문이 남는다.
  이 검사는 미검토·전체필드 unresolved인 합성 경계 입력이다.
  실제 후속 검토 성공이나 최종 전체 Profile 보존으로 주장하지 않는다.

## 과거 A와 현재 B 검사의 분리

- 기존 복구20개 테스트의 본문·지원 메서드는 AST 비교로 불변을 확인했다.
- 이미 있던 보존 코드 격리 실행기를 재사용했다. 기존 해시 검사는 유지한다.
  과거 A 블록·요청·v2/v3 재생·22개 요청 관측 검사4개를 해당 코드에서 추가 실행한다.
- 현재 B 요청은 새 분류 전송 테스트와 현재 빌더 검사에서 동결 B와 비교한다.
- 현재 v3 회귀는 저장 분류 결과 이후부터 시작한다. 저장 raw 분류를 현재 서버로 검증하여
  저장 파생 결과와 동일함을 확인한 후, 검토 이후3개 요청과 최종 응답을 정확 비교한다.
  A 응답을 B 모델이 새로 생성한 것처럼 주입하지 않는다.
- v3 기존 검토 통과27개·미검토112개·확인 후보52개, 검토 이견6개 보존 및
  기본v2 결과 동일성 검사를 유지했다. worker/HTTP/mock 경계와 지원하지 않는 계약 검사도 유지한다.
- 새 복구 기능·평가 도구·서비스 검증 단계는 만들지 않았다. 변경은 기존 테스트의
  버전/입력 경계 구성과 신규 B 통합 회귀에 한정한다.

## 실행 증거

결과 폴더: `E:/AgentFit/output/role-guidance-b-integration-20261003-v1`.

- 초기 RED: A 지침에서 B 요청2개 및 B 블록 해시 불일치를 확인했다.
  최초 테스트의 domain 필드명 오타도 수정했으며 첫 로그를 삭제하지 않았다.
- 관련 GREEN: B4건·v3보존12건·과거격리23건 통과.
- 첫 전체 unit1511건은 관측 테스트2건에서 과거22회와 현재분류이후3회 기대값 차이로 실패했다.
  과거 코드에서22개 요청을 계속 검사하고 현재3개 요청 전체를 검사하도록 분리했다.
  skip/expectedFailure 추가로 우회하지 않았다. 이전 실패 로그는 보존했다.
- 최종 전체 회귀 결과:

| 종류 | 실행 | 통과 | 실패/오류 | skip | 예상 실패 | 시간 |
|---|---:|---:|---:|---:|---:|---:|
| unit | 1512 | 1501 | 0 | 7 | 4 | 182.473초 |
| runtime | 39 | 39 | 0 | 0 | 0 | 168.299초 |
| 핵심 흐름 | 8 | 8 | 0 | 0 | 0 | 36.425초 |
| 계약 | 47 | 47 | 0 | 0 | 0 | 9.115초 |
| **전체** | **1606** | **1595** | **0** | **7** | **4** | 병렬 실행, 합산 벽시계 아님 |

- skip7건은 기존 선택 Docling 의존성6개와 Windows symlink1개다.
  예상 실패4건은 과거v2/v3 이름 역할과 Client 오분류의 원시 응답 검증이다.
  이번 변경으로 추가한 skip·예상 실패는0건이다.
- [최종 검증 기록](E:/AgentFit/output/role-guidance-b-integration-20261003-v1/final-verification.json)에
  4종 실행 명령별 로그·건수·시간·skip/예상 실패 상세와 과거격리24건을 기록했다.
- 외부 DNS/socket 전송 차단을 먼저 확인하고 로컬 mock/자식 프로세스 테스트만 실행했다.
  API 키 환경 변수를 테스트에서 제거했다. 모델 호출0, 유료 사용0.
- 독립 읽기 전용 검토: 승인 범위를 넘는 변경·회귀 완화 발견 없음.
  동결 gzip31개 해시도 별도 검증했다. 검토자는 전체 테스트를 따로 재실행하지 않았다.

## 보존과 남은 검증

- 변경 전 보호370개 파일 중 승인된 지침 파일1개만 변경, 나머지369개 동일.
  원본 평가 기록·골드·fixture·snapshot·manifest는 그대로다.
- `integration-audit.json`은 현재 서버 재판정과 원본을 분리한 새 결과이며 자동 마이그레이션이 아니다.
- 이번 확인은 **동결 지침의 코드 통합 및 오프라인 회귀**다.
  새 모델의 정확도, 다른 실제 문서 일반화, 40개 의미의 새 점수,
  실제 전체완주·호출 수·속도 개선, 운영 설정·배포·Spring은 미검증이다.
- 이름/유형/도메인 역할 및 지원 Client 구분의 실제 전체 흐름 개선은 후속 평가가 필요하다.
  원시 confirmed 오류, 텍스트 입력 연결 실패의 다른 유형, GLM 검토 오류·지연은 미해결이다.
- 큰 Goal은 paused 유지. 다음 실제 평가 및 약29분 병목의 검토 순서는
  [다음 평가 계획](next-document-evaluation.md)에 정리했다. 이번에는 실행하지 않는다.

## 변경 파일

- 서비스: `ai_service/agentfit_ai/candidate_mention_roles.py`.
- 신규 B 회귀: `ai_service/tests/test_frozen_role_guidance_b.py`.
- 현재 B 기대값: `test_tentative_proposed_preservation.py`, `test_mention_role_cause.py`.
- 보존 A 테스트 배치: `recovery_preserved_cases.py`, `recovery_version_fixture.py`,
  `test_review_recovery_versions.py`.
- 현재 downstream 재생/관측: `review_preservation_fixture.py`,
  `test_document_profile_v3_observer.py`, `test_document_profile_live.py`.
- 이 명세·계획·결과·다음 평가안과 `work/harness/frozen-role-guidance-b/STATE.md`.

기존 지침·모델 응답 기록 및 별도 작업의 미커밋 파일은 커밋 대상에서 제외한다.
로컬 기능 브랜치에 보존하며 이번 오프라인 범위에서는 원격 push·CI 실행을 하지 않는다.
