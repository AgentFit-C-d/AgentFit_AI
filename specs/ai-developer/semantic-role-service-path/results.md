# 의미 역할 검증: 서비스 경로 적용 결과

작성일: 2026-10-01. 서비스 연결과 이번 한정 검증을 완료했다. **새 문서의 실제 품질은 악화됐고 기존 문서의 변경 후 실행은 시간 초과했다. 운영 채택은 권하지 않는다.** 큰 goal은 paused를 유지한다.

## 적용 범위와 원인

기준 커밋은 `5de4020`, 작업 브랜치는 `feature/semantic-role-service-path`다. 선택형 의미 역할 분류기는 이미 있었지만 실제 NVIDIA 서비스 worker가 `semantic_assessment`를 전달하지 않아 기본값 `False`로 실행됐다.

변경은 `ai_service/agentfit_ai/analysis_worker.py`의 NVIDIA 분기에 `semantic_assessment=True`를 명시한 것이다. 문구·서비스명별 조건은 추가하지 않았다. 기존 공개 `confirmation-v2` 규격과 선택적 `modelDecisions`, `unassignedQuestions`를 그대로 사용한다.

```text
AGENTFIT_ANALYSIS_MODE=integrated-nvidia
POST /internal/v1/analyze
  → http_service._run_default_analysis(nvidia_only=True)
  → analysis_process.run_analysis_process
  → analysis_worker.execute_request
  → candidate_service_worker.execute_nvidia_analysis
  → candidate_analysis_pipeline.analyze_nvidia_candidates
  → analyze_integrated_candidates(semantic_assessment=True)
  → 근거 고정 → 의미 역할 분류 → 검토 → 기능 정리 → Profile 투영
  → worker / process / HTTP 응답 검증 → confirmation-v2
```

의미 분류는 대상 프로젝트·시점·부정·도입 여부·상충 근거와 mentionKind를 판단한다. 외부 서비스명은 외부 연동, 제품의 동작은 기능으로 제안할 수 있다. 역할·목적·설명 문구와 필드가 모순되거나 의미가 불명확하면 `needs_confirmation`으로 남긴다. 실제 모델이 역할 자체를 틀리게 판단하는 경우까지 규칙으로 보장하지는 못한다.

## 확인한 실행 환경과 미확인 배포 환경

| 항목 | 확인 결과 |
|---|---|
| 앱 기본 모드 | 환경변수 생략 시 `default`, Solar 경로 |
| `.env` | 앱이 자동 로드하지 않음. 루트 `.env`에는 키가 있으나 모드·내부 토큰 설정 없음. 키 값은 출력·기록하지 않음 |
| 조사 범위 | 작업 셸에 모드·내부 토큰·provider 키가 없음. 운영 실행 환경을 확인한 것은 아님. 평가 종료 후 별도 성공한 프로세스 조회에서 로컬 Python/uvicorn 잔류 0개 |
| 평가 서버 | 이번 worktree 코드, `integrated-nvidia`, 임시 내부 토큰, 요청 제한 1,800초·동시 요청 1을 명시적으로 주입 |
| 기본 체크아웃 | `E:/AgentFit`은 별도 `feature/semantic-review-model-routing`, `5e6910f`. 사용자 변경을 보존하고 수정하지 않음 |
| 운영 서버 | 배포 commit·실행 명령·환경변수 자료 없음. 적용 여부 미확인 |

운영 적용을 확인하려면 **배포한 commit/checkout, 시작 명령, 비밀을 제외한 `AGENTFIT_ANALYSIS_MODE`·요청 제한값, 환경변수/내부 토큰/키 주입 유무**가 필요하다. 키 값 자체는 필요 없다. 이번 작업은 배포하거나 실제 Spring 설정을 변경하지 않았다. 기본 Solar와 mixed 모드는 기존대로다.

## 후보 보존과 확인 상태

- 근거가 고정된 후보의 최초 판단 기록은 검토·기능 정리·Profile 투영과 별개로 유지한다.
- 불명확 후보는 `modelDecisions`에 원문 값, 문서 ID, 위치, 지지·반대 근거, 모델 분류와 서버 판단을 남긴다.
- 필드가 있으면 해당 필드를 `unresolved`와 질문으로, 필드도 미정이면 `unassignedQuestions`의 후보 ID로 보존한다.
- Profile에는 지지되는 제안만 넣는다. 같은 필드에 보류 후보가 있어도 정상 제안 값은 유지한다.
- `modelStatus=confirmed`와 사용자 승인·저장 완료는 다르다. 이번 통합 응답은 `outcome=needs_confirmation`; 실제 사용자 승인 및 Spring 저장을 수행하지 않았다.
- 원문 위치를 고정하기 전 거절된 항목은 기존 `rejected` 기록과 검토 보류 대상이다. 원시 추출 응답은 이 평가에 저장하지 않아, 특정 거절 항목을 특정 누락과 연결할 수 없는 경우는 미확인으로 표시한다.

## 고정 모델 응답을 사용한 실제 HTTP 회귀

이름·표현·문장 순서 변형, 원래 문서, 정상 연동/결제 기능, 의미 미정 후보를 포함한 같은 6입력·18후보를 전후 비교했다. 실제 LangExtract SDK·자식 프로세스·TCP/HTTP·최종 응답 검증을 실행하고 외부 모델 호출은 차단했다. **모델 역할 판단을 정답으로 주입한 시험이므로 실제 모델 정확도 수치가 아니다.**

| 지표 | 변경 전 | 변경 후 |
|---|---:|---:|
| 잘못된 최종 Profile 제안 | 6 | 0 |
| 정상 정보 누락 / 정상 정보 11개 | 0 | 0 |
| 확인 필요로 보존하지 못한 의미 미정 후보 | 1 | 0 |
| 반환한 질문 객체 수 | 11 | 12 |
| 의미 판단 보류 후보 | 0 | 7 |
| 후보별 최종 판단 기록 | 0 | 18 |
| 6요청 처리 시간 합계 | 7.495초 | 7.527초 |

변경 후 18개 후보 ID가 검토와 최종 기록까지 유지됐고, 보류 7개 모두 해당 필드 또는 미분류 질문에 연결됐다. 정상 11개는 유지됐다. 변경 전 기록 0개는 후보별 metadata가 없었다는 뜻이며 정상 정보까지 모두 유실됐다는 뜻은 아니다.

## 실제 모델 문서 평가

### 고정 조건

- 기존 [Documenso README](https://github.com/documenso/documenso/blob/a1d4bec1430a937395db9a4aae28979cd71c2831/README.md), 신규 [linkding README](https://github.com/sissbruecker/linkding/blob/27b7303baf41bb28babc610ac8eaa486e1ddfab5/README.md) 전체를 MARKDOWN으로 입력한다.
- 신규 문서는 선택 전에 기존 specs/harness/tests/output 기록을 검색해 사용 기록이 없음을 확인했다. 모델 사전학습 포함 여부는 알 수 없다.
- 문서·코드·평가기·정답을 호출 전에 해시로 고정했다. 추출·분류는 DeepSeek 4.1 Flash, 검토는 GLM 5.3, 전후 각 1회. 고정 후보 재생이 아닌 문서부터 새로 추출하므로 샘플링 변동도 포함한다.
- NVIDIA 계정 무료 이용·한도 초과 시 거절에 대한 기존 사용자 확인을 사용하고 매 호출 모델·endpoint·만료·호출 예산을 검사한다. 계정 잔여량이나 실제 청구를 직접 조회한 것은 아니다. 최대 4요청·256모델 호출, 재시도 0, 오류 시 전체 중단. 유료 대체 및 Luna 호출 없음.

### 지표 해석

정답은 호출 전 작성했지만 독립적인 사람 검토는 받지 않았다. 정상 명시 정보는 Documenso 9개, linkding 19개이며 전체 문서의 가능한 사실을 모두 망라하지 않는다. `false_proposals`는 사전에 정한 금지 역할/필드 조합의 탐지 수다. 별칭 부분 문자열 방식이므로 매칭은 전체 의미의 정확성을 보장하지 않는다. **0건을 문서 전체 오류 0건으로 해석하면 안 된다.** 정답 밖 출력과 셀프호스팅·배포 방식·라이브러리 용도 같은 모호 항목은 사람 검토로 분리한다. 질문 수는 정상 제안 승인 질문까지 포함한 실제 반환 객체 수다.

### 실측 결과

실제 4요청 중 3요청은 최종 Profile을 반환했고 마지막 요청은 시간 초과했다. 결과는 문서별로 구분하며, 실패 응답의 빈 출력을 정확도 개선으로 계산하지 않는다.

| 문서 / 경로 | 정상 유지 | 정상 누락 | 금지 역할 제안 | 질문 | 사전 정답 밖 출력 | 처리 시간 / 호출 |
|---|---:|---:|---:|---:|---:|---|
| linkding 변경 전 | 18/19 | 1 | 1 | 10 | 4 | 564.850초 / 10회 |
| linkding 변경 후 | 14/19 | 5 | 2 | 11 | 1 | 1,284.480초 / 14회 |
| Documenso 변경 전 | 7/9 | 2 | 0 | 10 | 4 | 1,399.580초 / 16회 |
| Documenso 변경 후 | 미검증 | 미검증 | 미검증 | 응답 없음 | 미검증 | 1,800.008초 / 15회 시작·14회 반환 |

변경 전 추적에서 `Clean UI optimized for readability`는 최초 의미 분류의 `features/confirmed` 판단이 검토 단계에서도 유지돼 Profile에 포함됐다. 확장 기능/북마클릿은 원문에 있지만 grounded 후보에 없고 Firefox·Chrome 이름만 있다. 이 단계에는 근거 위치가 모호해 거절된 24개 항목도 있으나, 원시 추출 텍스트를 보존하지 않아 확장 기능이 추출되지 않았는지 위치 검증에서 거절됐는지는 미확인이다.

변경 전 사전 정답 밖 4개 출력은 도메인 `bookmark manager`, 프론트엔드 `Node.js`, 배포 `Docker`, 기능 `tag auto-completion`이다. 앞의 기술·배포 분류에는 개발 도구/지원 설치 방식과 실제 채택 환경을 구분하는 검토가 필요하다. 마지막 기능은 원문에 있지만 이번 사전 정상 정답 목록 밖이므로 정상 유지 점수에 사후 추가하지 않았다.

**linkding의 실제 품질은 악화됐다.** 전후 grounded 후보 68개와 거절 기록은 완전히 같았다. 그 뒤 최초 분류부터 다음 차이가 발생했다.

| 사례 | 변경 후 최초 판단 / 후속 처리 | 최종 결과 |
|---|---|---|
| Firefox, Chrome | 모델이 `external_service/external_integrations/confirmed`, 서버 `supported`, 검토에서 유지 | 외부 연동 오류 2개 |
| 프로젝트명 linkding | 모델이 `product_operation/project_name/confirmed`; 서버가 역할·필드 모순을 보류 | Profile 이름 누락, 원문과 확인 의무는 유지 |
| Django | 모델이 `external_service/backend/confirmed`; 서버가 역할·필드 모순을 보류 | 정상 backend 제안 누락, 원문과 확인 의무는 유지 |
| JavaScript | 개발 관련 문장이라는 이유로 모델이 `non_product/other/irrelevant` 판단 | 정상 frontend 제안 누락, 제외 기록은 유지 |
| PWA | 모델이 `product_operation/features/confirmed`로 배치 | project_type 정상 항목 누락. 기능으로 나온 값은 사전 금지 규칙 밖이므로 추가 오류 점수에 넣지 않고 별도 검토 |
| 확장 기능/북마클릿 | 전후 모두 grounded 후보에 없음 | 정상 누락 1개 지속; 추출과 위치 거절 중 정확한 원인은 미확인 |
| Clean UI 설명 | 새 의미 분류에서도 `product_operation/features/confirmed`, 후속 검토에서 제외 | 이전 오류는 최종 Profile에서 제거됐지만 최초 의미 판단은 여전히 잘못됨 |

변경 후 최종 판단 기록은 68/68개, 후보 ID 유실 0개, 원문 값 불일치 0개다. 기록은 supported 16·보류 17·excluded 35개이며, 보류 17개 전부 질문과 연결됐다. 그중 필드 미정 13개는 질문 객체 1개로 묶인다. 따라서 질문 객체 증가 1개만 보고 사람의 검토 부담이 작다고 판단하면 안 된다. 기록의 supported는 최초 분류 결과로, 후속 검토에서 Profile 제안 3개가 제외돼 최종 Profile 항목은 13개다.

최초 분류 호출 수는 3→9회, 전체 호출은 10→14회, 시간은 약 2.27배로 늘었다. 이번 결과는 후보를 보존하는 서버 검증이 동작하더라도 **모델이 의미 역할 자체를 틀리면 정상 정보 보류와 새로운 오류가 동시에 생길 수 있음**을 보여준다. 서비스 연결 시험은 통과했지만 새 문서 품질 기준을 통과했다고 볼 수 없으며, 현재 브랜치의 운영 채택을 권하지 않는다.

Documenso 변경 전의 grounded 후보는 156개다. 이번 실제 실행에서는 Payments가 grounded 후보에 없었고 Stripe는 최초 분류부터 외부 연동으로 최종 Profile까지 유지됐다. 원래 Payments 오류를 재현하지 못했으므로 실제 모델에서 그 오류를 고쳤다는 근거로 쓰지 않는다.

이 문서의 정상 누락은 Postgres와 문서 서명 기능이다. Postgres의 두 표현 `Postgres SQL Database`, `postgres database`는 최초 분류와 검토 모두 `database/confirmed`였지만, 단일 값 필드에서 서로 다른 문자열이 둘 이상이면 값 없이 확인을 요청하는 기존 투영 규칙 때문에 `database=null`이 됐다. 따라서 이 누락의 최초 발생 지점은 **후처리**다. 문서 서명에 해당하는 사전 정답 표현은 grounded 후보에 없으며 원시 추출 응답 부재로 추출/근거 거절을 구분할 수 없다. 이 별도 원인에 대한 수정은 이번 서비스 연결 범위를 넓혀 수행하지 않았다.

Documenso의 사전 정답 밖 출력 4개는 TypeScript·Lingui·tRPC의 필드 분류와 셀프호스팅 관련 기능이다. 개발 언어·라이브러리 용도·셀프호스팅은 별도 사람 검토 대상으로 유지한다.

Documenso 변경 후는 의미 역할 분류 도중 HTTP **504 / ANALYSIS_DEADLINE_EXCEEDED**로 끝났다. 마지막 호출 schema는 `agentfit_semantic_assessment`였다. 최종 Profile·확인 질문과 단계 snapshot은 반환되지 않아 이 요청의 최종 품질과 후보 보존은 검증하지 못했다. 30분 제한을 늘리거나 추가 재평가하지 않았다.

`live-summary.json`의 실패 행에는 빈 응답 때문에 `false_proposals=0`, `normal_misses=9`가 계산돼 있다. 이는 의미 품질 점수가 아니다. 또한 `calls=0`, `grounded=0`은 종료 시 단계 trace 파일을 저장하지 못했기 때문이다. 실제 호출은 개별 시작/반환 기록으로 **15회 시작·14회 반환**을 확인했다. 별도 `final-candidate-inspection.jsonl`에서는 없는 trace를 `null`과 `trace_available=false`로 구분했다. 저장된 원본 결과는 수정하지 않았다.

전체 실제 호출은 **55회 시작·54회 반환**(DeepSeek 44회, GLM 11회), 마지막 1회는 로컬 요청 기한으로 중단됐다. 기록된 공급자 오류는 없으며 자동 재시도·유료 대체·Luna 호출은 0회다. 무료 범위 확인은 사용자 확인 기록에 근거했고 계정 청구 내역은 조회하지 않았다. 전후 실행 종료 후 고정 파일 262개의 해시 불일치도 0개였다. 지연은 네트워크·공급자 대기를 포함하는 1회 실측이며 순수 모델 속도나 RPM 효과를 분리한 실험이 아니다.

## 로컬 검증과 리뷰

| 검증 | 결과 |
|---|---:|
| 단위/worker 시험 | 1,279 실행, 1,272 통과·7 skip |
| 계약/mock 시험 | 47 통과 |
| 핵심 흐름 시험 | 8 통과 |
| 실제 SDK·프로세스·HTTP runtime 시험 | 36 통과 |

총 1,363 통과·7 skip. 최초 RED에서 서비스 경로의 metadata 누락과 역할 오류를 재현했다. 의미 분류 묶음 크기 변경으로 10후보 fixture의 호출 수가 5→6회가 되어 관련 fixture 기대값을 갱신했다. 8후보 이하 fixture는 5회 그대로이며 실제 서비스 호출 상한 64회는 유지한다. 최초 전체 실행 중 낡은 fixture 2건과 잘못 바꾼 소문서 호출 수 기대값을 수정한 뒤 각각 전체 suite를 재실행해 통과했다.

독립 읽기 전용 코드 리뷰: Critical/Important 없음. 부분 gold와 부분 문자열 채점의 한계를 보고에 명시하라는 Minor 의견을 반영했다. 리뷰 시점에는 실제 모델 결과가 아직 없어 정확도 판단을 보류했다.

수정 커밋 `4b54f60b2114b3285cd419cc93c2017df641a5cd`의 [CI 실행](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36829122975)은 `unit-and-worker-memory`, `contract-mock`, `core-flow-runtime`, `integrated-runtime` 4개 job 모두 성공했다. Push 후 고정 파일 262개의 해시 불일치 0개를 확인했다.

## 보존 위치와 종료 상태

전후 코드 snapshot/hash, 입력·정답·응답·단계 추적·로그는 `E:/AgentFit/output/semantic-role-service-path-v1/`에 보존한다. 핵심 파일은 `fixed-summary.json`, `live-summary.json`, `final-audit.json`, `final-candidate-inspection.jsonl`, 각 요청의 `response.json`이다. 기존 결과와 사용자 미커밋 변경은 수정하지 않았다. 평가 실행기는 정상 종료했고, 종료 후 로컬 Python/uvicorn 잔류 조회는 빈 목록이었다. 큰 goal의 paused 상태도 도구로 재확인했다.

## 결론과 미검증 사항

- **완료:** NVIDIA HTTP 서비스 경로 연결, 기존 v2 계약 유지, 실제 SDK/worker/HTTP 회귀, 새 공개 문서의 전후 평가, 성공 응답 내 후보·근거·확인 의무 보존 검증, feature 브랜치 push.
- **품질 기준 미달:** 새 문서의 오류 제안과 정상 누락이 증가했다. 원인은 최초 의미 역할 분류에서 관측됐고, 일부 잘못된 제안은 후속 검토도 통과했다. 단어 근거와 역할·필드의 형식적 일관성이 실제 의미의 정확성을 보장하지 않는다.
- **미검증:** Documenso 변경 후의 최종 정확도·후보 보존, 독립적인 사람 검토를 받은 전체 정답, 다른 새 문서에서의 일반화, 실제 사용자 확인 UI와 실제 Spring 저장, 운영 서버의 설정·배포 상태.
- **추가 확인에 필요한 정보:** 배포 commit/checkout, 시작 명령, 비밀을 제외한 모드·요청 기한과 환경변수 주입 유무. 실제 Spring 연결은 이번 범위에서 변경하지 않았다.
- 이번 결과를 운영 반영하지 않았다. 역할 분류 자체의 정확도와 정상 정보 보류 문제를 우선 재검토해야 하지만, 다음 실험이나 큰 goal을 자동으로 이어서 실행하지 않는다.
