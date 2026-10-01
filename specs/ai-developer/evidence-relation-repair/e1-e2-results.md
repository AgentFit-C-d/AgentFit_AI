# E1·E2 오프라인 구현 결과

## 범위와 결론

2026-10-01, `feature/candidate-evidence-audit`. 기준 커밋 `6cf018e`.
원문 위치 registry(E1)와 저장 응답 감사(E2)만 구현했다.
기존 field/status/verdict는 그대로 보존한다. 의미 관계 S1–S3는 구현하지 않았다.
새 모델/API 호출0, 서비스 적용0, 큰 goal은 paused다.
로컬 구현·검증은 약25분으로 요청한2시간 이내에 마쳤다.

## 보존 및 집계

동일 원문·후보·저장 응답과 기존 `audit.json` 기준을 사용했다.
표의 화살표는 **기존 저장 결과 → 새 오프라인 감사**이며 모델을 다시 평가한 결과가 아니다.

| 항목 | A | B |
| --- | ---: | ---: |
| 보존 후보/판정 | 68 → 68 | 68 → 68 |
| 원문에서 인용을 찾지 못함 | 2 → 2 | 4 → 4 |
| 인용은 있으나 해당 후보 위치를 포함하지 않음 | 10 → 10 | 18 → 18 |
| 인용 결함 합계 | **12 → 12** | **22 → 22** |
| 유효한 인용을 갖고도 기존 판정이 보류 | 12 → 12 | 15 → 15 |
| 기존 확인 필요 전체 | 24 → 24 | 37 → 37 |
| field/status/verdict 변경 | 0 | 0 |
| 후보·원응답 row 유실 | 0 | 0 |

- 전체 원문4558 code point, 132개 줄 단위, frozen 후보68개·기존 rejected24개를 보존했다.
- 입력·요약·freeze·payloads·18개 모델 원응답 등 원본22파일의 고정 해시가 일치한다.
  입력 파일을 수정하지 않고 별도 `originals/`에 바이트 단위로 복사했다.
- 감사 결과에는 원래 record와 원래 응답 row의 사본, 실제 후보 위치, 모델이 실제 인용한 위치를
  별도로 기록한다. 틀린 인용을 후보 위치로 바꿔 모델 선택이었다고 기록하지 않는다.
- 원문과 응답의 해시 불일치, 후보 중복/유실/범위 오류, 잘못된 단위 참조는 명시적으로 거절한다.
- 원문24000자/1000단위 초과 시 입력 전체를 보존하고 incomplete로 표시한다.
  선택은 support/counter 각각 최대8단위·4000자다. 부분 색인이나 가까운 위치로 대체하지 않는다.

## 구현

- `work/harness/evidence-relation-repair/source_registry.py`: 원문 hash와 정확한 `[start,end)`에
  연결되는 줄 단위, 반복·다중 줄 후보, 문맥과 제목 연결, 선택 단위 검증.
- `work/harness/evidence-relation-repair/legacy_audit.py`: 정확한 quote/occurrence 감사,
  원래 판정 보존, 파일 해시 검증과 덮어쓰기를 금지한 오프라인 replay.
- 서비스 코드·프로바이더 호출 코드·기존 A/B 분류기에는 변경이 없다. 새 의존성도 없다.

## 검증 결과

| 검증 | 결과 |
| --- | --- |
| E1 신규 회귀 | 10/10 통과 |
| E2 신규 회귀 | 16/16 통과 |
| 전체 단위 회귀 | 1329개 실행, 1322 통과·7 skip, 실패0 / 91.600초 |
| 실제 저장 파일 CLI 감사 | A68/B68, 결함12/22 재현 / 0.321초 |
| 모델을 새로 호출한 평가 | 미실행, 호출0 |

최종 독립 검토에서 Critical/Important/Minor 지적0. 검토자가 원본·복사본의 바이트와
해시를 확인하고 파일 쓰기 없이 집계를 다시 계산해 저장 결과와 일치함을 확인했다.

새 테스트는 미구현 상태의 실패를 확인한 후 구현했다. 실제 저장 응답을 고정해 재생한 로컬 검증이다.
반복 이름/문장, 다른 표 행, 줄바꿈을 합친 인용, HTML entity 불일치, Unicode/CRLF/탭,
원격 부정 문맥, 인용과 의미 오류가 동시에 있는 사례, 정상 정보 보존, 입력/선택 상한을 검증했다.
제목만 인용한 B C004–C007은 후보 위치를 찾아도 기존 보류를 유지한다.
Firefox·Chrome의 기존 잘못된 supported도 원형 보존되며 이번 작업이 해결한 것으로 세지 않는다.

## 다음 실제 모델 비교에 필요한 최소 변경 — 이번에는 미구현

1. 격리 비교기의 입력에 이 registry를 붙인다. A/B 양쪽에 **동일한 원문 전체·후보 위치·줄 단위 목록**을
   제공한다. 한쪽만 국소 문맥을 받게 하지 않는다. 기존 앞뒤240자 문맥도 정확히 보존한다.
2. 기존 quote/occurrence 출력 대신 support/counter **unit ID 선택**을 받는 프롬프트·스키마 어댑터를
   만든다. 기존 field/status 의미와 분류 방식은 유지하고, 서버는 `resolve_units`로 참조·범위만 검증한다.
   단위 목록 추가에 따른 입력 크기와 선택8단위/4000자 상한은 호출 전에 검사한다.
3. 새 응답은 별도 결과로 보관한다. 기존 기록은 덮어쓰지 않고 같은 후보/정답 분모로 인용 결함과
   의미 오류·정상 누락·보류·호출 수·시간을 따로 비교한다. 과거 confirmed를 자동 승격하는 연결은 만들지 않는다.

새 모델 비교는 별도 승인과 무료 이용 범위 확인 후에만 시작한다. B 추가 반복, S1–S3,
서비스 적용·Spring·배포·큰 goal 재개는 계속 보류한다.
새 계약을 모델이 제대로 선택하는지, 실제 정확도가 좋아지는지, 실제 호출 시간이 어떤지는 아직 미검증이다.
전체 회귀에서 건너뛴7개도 이번 실행의 통과 항목에 포함하지 않는다.

## 재현 자료

- 원본: `E:/AgentFit/output/direct-field-comparison-v1/` (변경 없음)
- 감사: `E:/AgentFit/output/evidence-source-audit-v1/audit.json`
- 원본 사본: `E:/AgentFit/output/evidence-source-audit-v1/originals/`
- 전체 테스트 로그: `E:/AgentFit/output/evidence-source-audit-v1/unit-tests.log`
- CI 독립 fixture: `ai_service/tests/fixtures/evidence_audit/saved_pair.json`

저장 파일 감사 실행(기존 output 경로를 다시 사용하면 거절):

```powershell
rtk proxy <venv-python> work/harness/evidence-relation-repair/legacy_audit.py --source E:/AgentFit/output/direct-field-comparison-v1 --manifest specs/ai-developer/evidence-relation-repair/audit.json --output <new-output-directory>
```

테스트는 `ai_service/`에서 `rtk proxy <venv-python> -m unittest discover -s tests -q`로 실행한다.
