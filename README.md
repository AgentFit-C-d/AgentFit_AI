# AgentFit AI

AgentFit의 문서 추출·분석, Profile 검증과 평가를 담당하는 AI 서비스입니다.
서비스 흐름은 Next.js → Spring Boot → FastAPI이며, PostgreSQL에는 Spring Boot만 접근합니다.

## 개발 절차

기능 구현 전에 `feature/<기능명>` 브랜치를 생성합니다. SDD 기반으로 명세(Spec) → 계획(Plan) → 작업 목록(Tasks) → 테스트 → 구현 → 검증 순서로 진행한 뒤, 해당 브랜치에 커밋하고 push합니다. 병합은 별도로 진행합니다.

## 로컬 환경 설정

루트 `.env` 파일에 `UPSTAGE_API_KEY`를 설정합니다. `.env`는 커밋하지 않습니다.
기능 브랜치의 `ai_service/` 디렉터리에서 Python 3.12로 Profile 단위 테스트를 실행합니다.

```text
python -m unittest discover -s tests -v
```

기능 범위와 검증 근거는 `specs/ai-developer/01-profile-contract/`에 있습니다.

## Solar 텍스트 분석 — 로컬 개발

`ai_service/` 디렉터리에서 Python 3.12로 고정된 합성 사례를 평가합니다.

```text
python -m agentfit_ai.evaluate --live
```

환경 변수 또는 루트 `.env`의 `UPSTAGE_API_KEY`를 사용해 6건을 분석합니다. 유료 API 호출은 정상 완료 기준 18~36회이며, 추가 패키지는 필요하지 않습니다. 보고서에는 평가 결과와 메타데이터만 기록합니다.

Python 모듈 `agentfit_ai.solar.SolarAnalyzer`는 문서 텍스트와 생성된 문서 ID를 받아, 근거 위치와 함께 검증된 Profile 초안을 반환합니다. 기본적으로 파일을 저장하지 않습니다. 로컬 진단 저장을 활성화하면 디버깅용 실패 응답을 보관할 수 있습니다.

명세·계획·작업 목록과 측정된 한계는 [Solar 분석 문서](specs/ai-developer/04-analysis-provider/README.md)에 정리되어 있습니다.

프롬프트 분리 실험(`profile-v18`) 당시 단위 테스트 70건, 기존 합성 평가 24/24건, 추가 합성 사례 2/2건, 실제 문서 평가 3/4건이 통과했습니다. 최종 평가에서 성공한 건은 모두 수정 호출 없이 통과했고, 실제 문서 1건은 시간 초과로 실패했습니다. 전체 품질 기준은 충족하지 못했습니다. 자세한 내용은 [프롬프트 분리 검증 결과](specs/ai-developer/04-analysis-provider/prompt-separation/validation.md)를 참고하세요. HTTP 엔드포인트, PDF 추출, Spring 연동은 향후 작업입니다.

고정된 안정성 평가도 실행할 수 있습니다. 분석 24건에 정상 완료 기준 유료 API 호출 72~144회가 발생하며, 네트워크 재시도는 하지 않습니다. 실행할 때마다 새로운 보고서 파일명을 사용합니다.

```text
python -m agentfit_ai.name_stability --live --report ../output/name-stability.json
```

[안정성 명세 및 검증 근거](specs/ai-developer/04-analysis-provider/stability/validation.md)

현재 실험 브랜치는 core·features 추출 후 별도 Solar 의미 검토를 수행합니다. 구조 수정 1회와 의미 수정·재검토 각 1회를 포함해 정상 완료까지 3~6회 호출하며, 오류로 조기 종료될 수 있습니다. 공개 Profile 형식은 유지합니다. 결과의 provider_calls, repaired_fields, first_pass_validated, semantic_reviewed로 처리 상태를 확인합니다. 검토는 medium/8192, 추출·수정은 none/4096 설정입니다.

semantic_review=False는 비교 평가용으로 검토를 생략하며 결과에 표시됩니다. 모델 검토 통과가 의미 정확성을 보장하지 않습니다. 전체 60초 예산을 호출 전후 검사하지만, urllib의 블로킹 통신을 강제로 중단하는 하드 시간 제한은 보장하지 않습니다.

## 호출 진단 — 로컬

`ai_service/` 디렉터리에서 진단 파일 저장을 명시적으로 활성화합니다.

```text
python -m agentfit_ai.evaluate --live --diagnostics-dir ../output/diagnostics --report ../output/new-evaluation.json
python -m agentfit_ai.diagnostics --directory ../output/diagnostics
```

파일 저장을 활성화하지 않아도 분석 결과와 오류에서 호출별 진단 정보를 확인할 수 있습니다.

진단 기록에는 처리 시간, 크기, 사용량, 민감 정보를 제외한 오류 메타데이터가 포함됩니다. 최종적으로 분석이 실패한 경우에만 해당 분석의 실패 호출 원본 응답을 저장합니다. 수정 후 성공한 분석의 원본 응답은 저장하지 않으며, 민감 정보가 있거나 파싱할 수 없는 응답도 제외합니다.

로컬 기록의 보관 기간은 7일입니다. 읽기·쓰기 또는 명시적 정리 명령 실행 시 만료된 기록을 삭제합니다. 프로세스가 중지된 동안에는 파일을 삭제할 수 없으므로, 배포 환경에서는 주기적인 정리와 접근 통제가 필요합니다. Windows에서는 디렉터리에서 상속된 접근 권한(ACL)을 사용합니다.

호출 진단 기능 검증 당시 단위 테스트 86건과 실제 API를 사용한 합성 분석 6건이 통과했습니다. 이 기능은 호출 상태를 추적하기 위한 것으로, 앞서 확인된 제공자 응답 시간 초과 문제는 남아 있습니다.

[호출 진단 명세 및 검증 결과](specs/ai-developer/04-analysis-provider/call-diagnostics/validation.md)

## 역할 분류 실험 — profile-v21

단위 테스트 99건이 통과했습니다. 기존 합성 평가 24/24건, 추가 기능 사례 2/2건, 신규 역할 분류 사례 5/8건, 기존 실제 문서 평가 3/4건, MABC README 평가 0/2건이 통과했습니다.

**전체 품질 기준은 아직 충족하지 못했습니다.** 현재 기능 브랜치는 실험 단계이며, 운영 적용을 위한 검증이 완료되지 않았습니다.

[검증 결과와 남은 오류](specs/ai-developer/04-analysis-provider/role-classification/validation.md)

## 원문 후보 ID 선택 실험 — profile-v23

서버가 원문에 부여한 ID 범위를 Solar가 선택하고, 서버가 기능명과 근거 위치를 복원하도록 구현했습니다. 공개 Profile 형식은 유지합니다.

단위 테스트 110/110건과 실호출 40/40건의 최종 구조 검증을 통과했지만, 의미 품질은 기존 합성 18/24건, 추가 기능 1/2건, 역할 분류 3/8건, 기존 실제 문서 2/4건, README 0/2건으로 기준에 미달했습니다. 이전 버전보다 의미 정확도가 낮아지고 입력 토큰이 늘어 **운영 적용을 권장하지 않습니다.**

이 ID 선택 경로는 현재 실험 브랜치에서 제거하고 v21 추출 방식으로 복귀했습니다. 당시 결과와 이력은 보존합니다.

[후보 ID 실험 결과와 제약](specs/ai-developer/04-analysis-provider/source-candidates/validation.md)

## 의미 검토 실험 — profile-v27

Solar 검토·제한된 수정·재검토와 실패 응답 보관을 구현했습니다. 단위 테스트117건이 통과했지만 의미 품질은 아직 승인되지 않았습니다. 작은 비교 결과와 남은 제약은 [의미 품질 검증](specs/ai-developer/04-analysis-provider/semantic-quality/validation.md)을 확인하세요.
