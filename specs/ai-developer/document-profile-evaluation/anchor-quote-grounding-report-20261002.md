# 텍스트 입력 후보 원문 위치 연결 — 오프라인 수정 결과

2026-10-02 · 기반 `e5ec802` · 브랜치 `feature/anchor-quote-grounding`

## 결론과 범위

저장된 operation 응답에서 ASCII/곡선 큰따옴표 차이로 실패한 원문 위치 연결을 재현하고 수정했다. 목표 후보의 위치는 복구됐다. 새 후보의 의미 분류·검토·최종 Profile은 실행하지 않았으므로 **최종 의미 보존과 기존 40개 의미의 새 누락 수는 미측정**이다.

큰 Goal은 paused다. 새 모델 호출·재시도·외부 네트워크 전송·배포·Spring 변경은 모두 0이다. 이번 외부 전송 금지에 따라 Git push도 하지 않는다. 모델·프롬프트·골드·의미 분류·검토 정책·v3 계약은 변경하지 않았다.

## 1. 수정 전 재현

동결 trace 호출 3의 `mentions[18]`:

```text
quote: PDF · Markdown · 텍스트 입력
model anchor: A[“GitHub 로그인 · 개인 프로젝트 생성”] --> B[“PDF · Markdown · 텍스트 입력”]
source anchor: A["GitHub 로그인 · 개인 프로젝트 생성"] --> B["PDF · Markdown · 텍스트 입력"]
```

기존 정확 일치 함수는 `ambiguous_anchor`, start/end=null을 반환한다. 후보 값이 없는 문제가 아니라 anchor의 U+201C/U+201D와 원문의 U+0022 차이다. 정확 일치 전용 결과는 저장된 `operations_grounded`와 완전히 일치했다. 신규 테스트의 최초 실행에서도 저장 후보 복구·유일 위치 복구 등이 실패했고, 수정 후 통과했다.

동결 fixture 7개 파일의 SHA를 검증했다. 주요 해시는 다음과 같다.

| 자료 | SHA-256 |
|---|---|
| trace.json | `703d98e7fe11cf50dc59b06c6fb0b053bc8d69d935f97cad541b6e6c8f962158` |
| document.txt / source.md | `9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451` |
| gold.json | `40ecc131c19fb8aa0e0127b67f9a5adf95885ed194a67350d3c89a9e9b328260` |

원본과 압축 fixture는 수정하지 않았다.

## 2. 최소 변경

- `anchored_grounding.py`: 정확 anchor가 아예 없을 때만 선택적으로 U+201C/U+201D를 ASCII 큰따옴표로 비교한다. 정확 anchor가 반복되는 경우에는 보조 연결로 우회하지 않는다.
- `operation_candidates.py`: 해당 보조 연결을 operation 추출에서만 활성화한다. 다른 소비자는 기존 기본값인 정확 일치만 사용한다.
- 비교 anchor가 문서 전체에서 유일하고, 후보 값이 제공 anchor 안에 정확히 한 번 있어야 한다. 성공 전 `document[start:end] == quote`를 검사한다.
- 변환은 Unicode 코드포인트 1개→1개다. CRLF·한글·이모지 포함 원문은 수정하지 않고 원본 인덱스를 그대로 사용한다. UTF-8 바이트 오프셋이나 UTF-16 코드 유닛 위치가 아니다. end는 제외한다.
- 공백·대소문자·작은따옴표·backtick·Unicode 조합·문장부호 차이, 일반 유사도나 가까운 문장 탐색은 처리하지 않는다. 후보 값 자체도 정규화하지 않는다.
- 기존 중복 위치와 interval 충돌은 계속 거절한다. 의미 분류나 긍정 채택은 이 함수의 역할이 아니다.

## 3. 저장 응답 재생 결과

| operation 위치 연결 지표 | 수정 전 | 수정 후 |
|---|---:|---:|
| 동일 저장 응답의 mention 수 | 57 | 57 |
| 원문 위치 연결 성공 | 42 | 57 |
| 위치 연결 실패 | 15 | 0 |
| 기존 42개 연결의 변경·유실 | — | 0 |

목표 후보의 복구 내용:

```json
{
  "documentId": "PUBLIC-01",
  "operationMentionIndex": 18,
  "sourceValue": "PDF · Markdown · 텍스트 입력",
  "start": 1890,
  "end": 1913
}
```

`document[1890:1913]`가 위 값과 정확히 같다. 여기서 sourceValue는 감사 도구가 원문에서 직접 자른 값이다. 아직 새 후보에 대한 최종 확인 응답이나 Profile이 생성된 것은 아니다.

같은 다이어그램의 다른 후보 14개도 동일한 따옴표 결함으로부터 복구됐다. 특정 ID·문구 예외 없이 같은 규칙을 적용한 결과다. 전체 목록은 `E:/AgentFit/output/anchor-quote-grounding-20261002/recovered-locations.json`에 보존했다.

기존 합쳐진 145개 위치와 복구된 위치의 합집합은 160개다. 이 수치는 후속 모델 요청의 후보 구성과 ID가 달라질 수 있음을 보여준다. **operation 위치 실패 0건을 문서의 정상 의미 누락 0건으로 해석할 수 없다.**

## 4. 후속 판단 재사용 차단 및 v3 회귀

저장된 호출 3 요청과 현재 operation 요청이 정확히 같은지 확인하고 응답 1개만 메모리에서 재생했다. 새로운 분류 호출은 차단했다.

수정된 후보 집합에 기존 분류 응답을 연결하려 하면 저장 요청 비교에서 불일치로 중단된다. 이 비교를 완화하거나 새 후보에 옛 판단·정답을 끼워 넣지 않았다. v3 회귀의 시작 경계를 명시적으로 저장된 `operations_grounded` 이후로 옮겨 기존 145개 후보만 사용한다. 이후 요청 4–25의 payload를 모두 정확히 비교한 뒤 저장 응답을 재생한다.

따라서 v3 테스트는 기존 후보에서의 검토 보류 기능 회귀 검사다. 현재 추출부터 시작하는 새로운 전체 분석 결과가 아니다. 기존 v2 결과 완전 동일성, 원시 판단, 검토 통과 27개·미검토 112개·기존 확인 후보 52개, 별도 보류 6개와 질문 11개에 대한 기존 검증을 유지했다.

## 5. 로컬 검증

| 검증 | 결과 |
|---|---|
| 이번 위치 연결 회귀 | 12/12 통과 |
| 기존 v3 회귀 | 18/18 통과 |
| 독립 리뷰 관련 회귀 | 52/52 통과, 추가 수정 사항 없음 |
| 최종 오프라인 전체 | 1,404 통과 / 7 skip / 실패·오류 0, 총 1,411건 |
| 전체 테스트 시간 | 43.692초 — 모델 처리 시간이 아님 |
| 네트워크 테스트 | TCP를 사용하는 29건 의도적으로 제외 |

위 부분 집합은 전체 테스트에 포함되며 합산하지 않는다. skip 7건은 선택 Docling 의존성 6건과 플랫폼 symlink 1건이다. 응용 소켓·기본 provider transport는 차단했다. ASGI 메모리 전달과 로컬 저장 응답만 사용했다.

회귀 범위: 기존 정확 연결 우선, 큰따옴표 차이 양방향, 동일 문구 반복과 유일 문맥, 후보가 anchor에 없음, 틀린 문맥, CRLF·한글·이모지 원본 위치, 원문/입력 불변, duplicate span과 interval 충돌, 비대상 정규화 거절, 부정·다른 프로젝트 표현의 원문 후보 유지 및 의미 라벨 미생성, 기존 v3 동작.

재현 명령(ai_service 디렉터리):

```powershell
rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -X utf8 tests/anchor_quote_audit.py E:/AgentFit/output/anchor-quote-grounding-20261002 --suite
```

결과 폴더에는 summary.json, recovered-locations.json, before-operations.json, after-operations.json, unit-tests.txt, test-summary.json이 있다.

## 6. 미확정 위치와 남은 한계

현재 operation 실패 자료는 `{index, reason}`이며 유효한 source span이 없다. v3의 reviewDispositions는 이미 원문에 연결된 modelDecisions 후보 ID를 참조한다. 따라서 **위치가 미확정인 개별 후보를 현재 v3의 근거 연결 확인 대상으로 전달할 수 없다.** 미정 필드 처리는 별개이며, 이를 지원하려면 별도 계약 확장이 필요하다. 이번에는 기존 실패 경로를 유지했다.

- 복구 후보의 의미 분류·검토 결과, 최종 Profile 보존·보류·누락, 기존 40개 의미의 수정 후 점수: 미측정.
- Codex 외부 연동 오분류, 프로젝트명 분류, 의미 검토의 품질, 실제 모델 처리 시간: 미해결.
- 모델이 후보 값 자체의 따옴표를 바꾸거나 공백·다른 문자까지 바꾸는 경우: 보수적으로 실패 유지.
- 실제 모델 요청·운영 HTTP·실제 Spring·서비스 적용: 미실행.

## 변경 파일

제품 코드 2개 외에는 테스트·감사·작업 기록이다.

- ai_service/agentfit_ai/anchored_grounding.py
- ai_service/agentfit_ai/operation_candidates.py
- ai_service/tests/test_anchor_quote_grounding.py
- ai_service/tests/anchor_quote_audit.py
- ai_service/tests/review_preservation_fixture.py
- ai_service/tests/review_preservation_audit.py
- specs/ai-developer/document-profile-evaluation/anchor-quote-grounding-plan-20261002.md
- specs/ai-developer/document-profile-evaluation/anchor-quote-grounding-report-20261002.md
- work/harness/document-profile-evaluation/STATE.md

다른 작업의 변경은 보존했다. 오프라인 구현·검증 결과 보고로 종료한다.
