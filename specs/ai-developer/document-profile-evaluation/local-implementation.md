# 현재 서비스 분석 경로의 기준 평가 — 로컬 구현

## 승인 범위와 구현 선택

2026-10-02 사용자 요청으로 기존 기대값을 승인 기준으로 사용한다. `gold-draft.json`의 내용·정답 기준은 그대로 보존했으며 승인과 파일 해시는 `baseline-contract.json`에 별도로 기록했다. `meaning-units.json`에는 기능 36개와 기능 외 4개의 의미 ID를 부여했다. 골드를 모델 입력으로 사용하지 않는다.

U/US 분류기를 삽입하지 않는다. 현재 서비스가 제공하는 `integrated-nvidia` 경로의 `analysis_worker.execute_request`를 그대로 실행하고, 이 함수가 지정하는 `semantic_assessment=True`와 기본 모델들을 사용한다. 기본 코드 모드 `default` 및 실제 배포 환경이 이 모드로 설정돼 있다는 주장은 하지 않는다.

기존 계획의 직접 함수 연결보다 현재 worker를 재사용하는 편이 경로 차이를 줄인다. `diagnostic_tools/document_profile_worker.py`는 기존 후보 관측 worker 관례에 따라 **평가용 자식 프로세스 안에서만** 관측을 설치하고 원래 worker 출력 바이트를 유지한다. 상주 HTTP 서버에 설치하거나 기본 진입점으로 변경하지 않는다.

## 최소 변경

- 서비스 코드 변경은 `candidate_analysis_pipeline.py`의 선택형 `detail_observer` 추가뿐이다. 기존 4단계 observer 계약과 프롬프트·분류·스키마·검토·최종 판정은 유지했다.
- 기존 `CandidateTrace`를 재사용해 grounded/classified/reviewed/projected의 연결을 검증한다.
- 추가 기록: 일반 추출 결과, 위치 연결 결과, 동작 후보, 병합 입력, 의미 판정의 modelDecisions, 검토 완료 결과, 기능 대표 선정의 전체 그룹.
- 요청·응답은 평가 전용 파일에 기록한다. 인증 인자는 기록하지 않으며 기존 비밀 값 제거 함수를 재사용한다. 레코드 2 MiB, 전체 32 MiB를 넘거나 비밀 값 제거로 기록이 불완전해지면 관측 오류로 남긴다. 이를 완전한 평가로 채점하지 않는다.
- 네트워크 기본 동작을 가진 새 평가 CLI는 제공하지 않는다. 준비 CLI는 키를 읽지 않고 `execute=True`를 거절한다. 실제 실행을 승인받은 다음 기존 부모 프로세스의 시간 제한과 무료 이용 검사를 연결해 이 worker를 실행한다.

## 원문부터 기록까지

1. 실제 Markdown 바이트를 `extract_document`로 읽고 원문 바이트/추출문 해시를 따로 기록한다. 원본 CRLF를 보존한다.
2. 저장 후보를 주입하지 않고 실제 LangExtract/동작 추출기를 거친다. 골드·후보 파일을 받는 분석 인터페이스가 없다.
3. 모델 요청의 전체 system 지침·스키마·문맥과 반환 응답을 기록한다. 일반 추출은 SDK가 만든 구간이고 나머지 기존 단계는 기존 payload 그대로다.
4. SDK 정렬 전 원시 응답은 calls 기록으로, SDK 추출 결과는 general_extracted로 확인한다. 원시 응답에는 있지만 SDK/위치 연결 단계에서 빠진 것은 모델 추출 누락과 구분한다.
5. 최종 Profile뿐 아니라 modelDecisions·fieldStates·questions를 함께 남겨 불확실한 후보의 완전 유실을 구분한다.
6. 첫 실패에서 기존 서비스 경로가 중단한다. 자식 시간 초과/강제 종료로 sidecar가 완성되지 않았으면 기록 미확보이며 성공 또는 누락 0건으로 보지 않는다.

## 의미 보존 채점 방법

채점기는 문자열 포함이나 대표 기능 개수를 점수로 사용하지 않는다. 원문·후보·최종 표현을 읽은 평가자가 40개 의미 ID별로 다음 판단을 기록하고 코드가 계수한다.

`추출 → 위치 연결/병합 → 분류 → 검토 → 대표 선정 → Profile → 최종 응답`

- 상태: preserved / missing / wrong / held / human_review. 실제 단계 기록이 없으면 unobserved.
- preserved/held에는 해당 단계의 JSON pointer와 판단 근거가 필요하다. 문구가 달라도 동일 동작을 보존하면 인정하고, 포괄적인 이름만 붙여 세부 동작이 빠졌으면 누락이다.
- 골드·실행 기록 해시를 대응표에 묶는다. 다른 실행의 대응표를 재사용하거나 의미 단위를 빼는 경우 거절한다.
- 최초 오류 단계에만 원인을 귀속한다. 분류 오류 후 하위 단계 누락을 후처리 오류로 중복 계산하지 않는다. 최종 누락·보류는 별도 결과 지표다.
- 정상 정보의 최종 누락에는 보류만 된 정보도 포함하되, 완전 유실과 보류 수를 분리한다.
- 명시적 없음·미정·범위 밖 항목 16개는 개별 문맥 판정표에 남긴다. 정답이 애매한 의미는 human_review로 보류한다.
- 오확정 감사는 모델 confirmed 레코드와 최종 긍정 값 모두의 참조를 확인해야 완료된다. 미감사를 오확정 0건으로 표기하지 않는다. 인용 결함도 별도 수동 감사다.
- 모델 판정과 최종 응답의 관측 여부를 각각 확인한다. 첫 호출 실패 등으로 미관측이면 오확정·인용·질문 지표는 null이며, 모든 단계의 의미 검토를 마쳐야 전체 채점을 완료로 표시한다. 최초 오류 귀속 완료와 전체 검토 완료는 별개다.
- 사용자 승인 질문과 AI 불확실성 질문을 나눈다. 모델 confirmed가 사용자 확정으로 저장됐다는 의미로 보고하지 않는다.

**한계:** 의미 대응은 사람이 검토하는 방식이다. 코드가 의미의 정답을 자동 증명하거나 별도 모델로 채점하지 않는다. 10필드의 null/값 상태 적합성과 36개 기능 의미의 보존은 별도 지표다.

## 실행 명령 (전부 로컬 준비/채점)

`ai_service` 디렉터리에서:

```powershell
rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m diagnostic_tools.document_profile_evaluation --source E:/AgentFit/Docs/project-proposal.md --output E:/AgentFit/output/document-profile-baseline-preparation-v1
```

출력 폴더는 덮어쓰지 않는다. 위 명령은 이번에 이미 실행했으므로 재실행 시 다른 폴더명을 사용한다. 실제 모델 호출 없이 preflight·원문·파서 출력만 만든다.

실제 trace가 준비된 뒤 대응표 생성 및 사람 검토 후 채점:

```powershell
rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m diagnostic_tools.document_profile_scoring --trace TRACE.json --gold ../specs/ai-developer/document-profile-evaluation/gold-draft.json --output alignment.json
rtk proxy E:/AgentFit/tmp/worktrees/analysis-runtime/.venv/Scripts/python.exe -m diagnostic_tools.document_profile_scoring --trace TRACE.json --gold ../specs/ai-developer/document-profile-evaluation/gold-draft.json --alignment alignment.json --output metrics.json
```

`alignment-preview-not-executed-v2.json`은 미실행 상태의 모양만 보여준다. 실제 trace의 대응표로 재사용할 수 없다. 초기 미리보기는 보존하고, 리뷰 수정 후 미관측 지표를 null로 표시한 v2를 별도 저장했다.

## 로컬 검증 결과

- 최종 단위 테스트: **1,410건 중 1,403건 통과, 7건 skip**, 80.385초.
- 런타임 테스트: **39건 통과**, 151.673초. 실제 SDK·HTTP·자식 프로세스와 로컬 합성 응답으로 검증했다. 이후 변경은 오프라인 채점기와 그 회귀 테스트뿐이며 런타임 경로는 바뀌지 않았다.
- 신규 테스트: 준비/관측 5건, 의미 채점 12건, 서비스 경로 비교 3건. 실제 `/internal/v1/analyze`와 관측 worker의 모델 요청 및 최종 출력이 합성 응답에서 동일함을 확인했다.
- 독립 리뷰에서 미관측 지표의 잘못된 0 표시와 중간 단계 미검토의 완료 표시를 발견했다. 3개 회귀 테스트가 수정 전 실패했고 수정 후 통과했다.
- 실제 모델 호출 **0회**. 합성 테스트 통과는 AgentFit 문서의 실제 모델 품질을 뜻하지 않는다. 의미 36개는 전부 미평가 상태다.
- 원문·승인 골드 내용·분모를 유지했다. 문서는 기존 개발에 사용된 AgentFit 기획서이므로 새 문서 일반화 성능의 근거가 아니다.
- 운영 배포의 실행 모드와 실제 Spring 저장은 미검증이다.

## 실제 호출 전 제안

문서 1개, 서비스 흐름 1회. 새 후보 수를 N(최대 240), 분류 후 확정 후보 수를 C(0≤C≤N)라 한다.

| 단계 | 모델 | 호출 수 |
| --- | --- | --- |
| 일반 후보 추출 | `deepseek-ai/deepseek-v4.1-flash` | 2회 — 설치된 LangExtract 1.7.0의 RegexTokenizer/4,000자 버퍼로 로컬 계산 |
| 동작 후보 추출 | 같은 DeepSeek | 1회 |
| 의미 분류 | 같은 DeepSeek | ceil(N/8)회 |
| 확정 후보 검토 | `z-ai/glm-5.3` | ceil(C/20)회 |
| 원문 누락 검토 | 같은 GLM | 1회 |
| 대표 기능 선정·기존 검토/보완 | DeepSeek | 0~4회 — 기존 서비스의 조건부 단계 그대로 |
| Profile/확인 응답 생성 | 서버 규칙 | 0회 |

계산식은 **4 + ceil(N/8) + ceil(C/20) + K**, K=0~4다.

- 예시 가정 N=40/C=25: 11~15회, N=80/C=60: 17~21회, N=120/C=80: 23~27회. 후보 수 분포를 아직 측정하지 않았으므로 통계적 예측이 아니다.
- 현재 문서의 2개 추출 구간과 후보 상한에서 계산상 최대 **50회**다. 서비스의 안전 상한 **64회**는 유지한다. 36개 의미 수를 후보 수로 간주하지 않는다.
- 제안 전체 제한: **64회 / 총 1,800초(30분) / 호출당 최대 600초 / 네트워크 재시도 0회 / 첫 실패 중단**. 현재 서비스 기본 요청 상한과 같다.
- 기존 기능 요약 보완은 위 K에 포함되는 기존 단계다. 새 관계 검증기나 U/US 단계를 더한 것이 아니다.
- 실제 실행 시 무료 NVIDIA endpoint 조건을 확인해야 한다. 현재 준비에서는 재확인·실제 호출을 하지 않았고 유료 전환·충전·대체 호출은 허용하지 않는다.
- 운영 배포와 Spring 저장은 범위 밖이다. 큰 goal은 재개하지 않는다.
