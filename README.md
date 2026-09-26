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

## 순번 오류 보완 실험 — profile-v28

기능 인용의 등장 순서 설명과 항목별 수정 진단을 추가했습니다. 단위121건은 통과했지만 실제 실패 초안 수정은 실패했고, 합성 정확도는2/3이었습니다. 운영 적용을 위한 품질 개선은 입증되지 않았습니다. [검증 결과](specs/ai-developer/04-analysis-provider/occurrence-repair/validation.md)와 [전체 필드 공통 근거 계약 설계안](specs/ai-developer/04-analysis-provider/evidence-contract/spec.md)을 참고하세요. 공통 계약은 사용자 승인 후 별도 feature/shared-evidence-contract 브랜치에 구현했습니다.


## 공통 근거 계약 — profile-v30

10개 필드의 값과 근거를 항목별로 묶고, 서버가 원문과 정확히 일치하는 위치를 계산합니다. 같은 인용이 여러 번 나오면 원문에서 유일한 문맥을 요구하며, 임의의 첫 위치를 고르지 않습니다. 중복 값·원문에 없는 인용·다른 항목의 근거·잘못된 상태와 역할은 거절합니다.

미언급은 JSON null, 명시적 없음은 근거가 있는 absent, 확정은 confirmed로 구분합니다. 모델의 역할 분류와 의미 판단이 맞다는 보장은 별도의 평가가 필요합니다. 공개 Profile과 최대6회·60초 예산, 실패 원본7일 정책은 유지합니다.

기본 내부 계약은 evidence-v1입니다. evidence_contract=False는 과거 줄번호/등장순서 방식의 비교용 옵션이며 자동 fallback은 없습니다. semantic_review=False도 비교용입니다. 새 계약의 확정성 검사는 짧은 인용이 속한 원문 줄을 확인합니다.

[공통 계약 명세](specs/ai-developer/04-analysis-provider/evidence-contract/spec.md) · [검증 결과와 남은 과제](specs/ai-developer/04-analysis-provider/evidence-contract/validation.md)

공통 계약 검증: 단위140/140, 최종 실호출 정답1/7·오답반환1·오류5. 두 차례 중단의 미확인 시도는 별도 기록했습니다. 전체 분석 품질 기준은 미충족이며 운영 적용을 보류합니다.

## 구조 보존 구역 분석 실험 — section-v1

별도 agentfit_ai.section_analysis.SectionAnalyzer에서 제목·문단·표·코드블록과 원문 위치를 보존해 모든 구역을 최대2묶음으로 처리합니다. 검증된 사실 후보의 ID만 통합하고 최종 검토를 거칩니다. 기본 SolarAnalyzer는 변경하지 않았습니다.

묶음당12000자,최대6회 호출·60초 예산입니다. 상한 초과·구역 누락·근거 오류는 부분 성공으로 반환하지 않습니다. 임베딩이나 벡터DB는 사용하지 않습니다.

전체163테스트는 통과했지만 실제 고정 평가0/7로 개선 효과를 입증하지 못했습니다. 운영 채택을 보류합니다. [실험 결과·지원 범위·제약](specs/ai-developer/04-analysis-provider/section-analysis/validation.md)

## 후보별 단일 판정 실험 — section-v2

구역 분석기의 통합 응답을 후보ID별 판정 하나로 바꿨습니다. 선택/제외를 동시에 출력하는 모순을 없애고 기존 역할·충돌 검증을 유지합니다.

전체166테스트는 통과했지만 고정7사례는 모두 추출 단계에서 실패했습니다. 수작업 후보 통합2회도 실패했으며, 계측한 두 번째 호출에서 잘못된 역할 선택을 확인했습니다. **의미 품질 개선은 입증되지 않았으며 기본 분석기를 유지합니다.** [검증 결과와 다음 과제](specs/ai-developer/04-analysis-provider/section-decisions/validation.md)

## Solar Mini 4 비교

분석기 생성자에 model="solar-mini4"를 지정하면 추출·통합·검토·수정에 모두 Mini를 사용합니다. 기본 모델은 solar-pro4입니다. API 키는 기존 Upstage 키를 사용합니다.

동일 section-v2 조건의7사례에서 Mini도 정답0/7이었습니다. 모델 교체만으로 품질 개선은 확인되지 않았습니다. 전체168테스트는 통과했습니다. [모델별 결과 및 한계](specs/ai-developer/04-analysis-provider/solar-mini4/validation.md)

## Solar Jev 역할 판정 실험

단일 후보를 운영/개발/미정/예시/과거/미언급으로 구분하는 독립 합성 실험입니다. 기존 분석기에 연결하지 않았습니다.

12사례를 선택지 정순·역순으로24회 호출해21/24 정답, 순서 일관성11/12쌍, 운영 오탐0건을 기록했습니다. 중앙값274ms이며 사전 통과 기준에는 미달했습니다. 전체 문서 추출 평가와 직접 비교할 수 없습니다.

실행(ai_service에서): python -m agentfit_ai.jev_evaluation --live --output ../output/jev-new-run
출력 디렉터리는 새 경로여야 하며 기존 결과를 덮어쓰지 않습니다. [명세 및 검증 결과](specs/ai-developer/04-analysis-provider/solar-jev/validation.md)

## Mini4 + Jev 구역 분석 통합 실험

SectionAnalyzer(key, model="solar-mini4", jev_merge=True)로 Jev가 후보 통합과 의미 수정을 맡도록 선택할 수 있습니다. 추출/최종 검토는 Mini4이며 기본 동작은 바뀌지 않습니다.

동일7사례에서 기존 Mini4 0/7 → 통합1/7 정답을 관측했습니다. 추출 응답도 달라져 Jev 단독 효과로 확정할 수 없습니다. 실패6건 중5건은 Jev 이전 추출 오류였고 실제 문서2개는 모두 실패했습니다. 전체179테스트 통과. [단계별 결과와 제약](specs/ai-developer/04-analysis-provider/jev-integration/validation.md)

## 단일 인용 추출 실험

구역 분석기에 quote_only=True를 지정하면 AI가 값과 인용을 따로 생성하지 않고, 서버가 정확한 인용에서 값을 복원합니다. 인용 불일치·모호함·구역 누락 등은 안전한 세부 원인으로 진단합니다.

짧은 합성6개는 구조검증6/6, 사전 정답기준0/6이었습니다. 추가 확인에서 정확한 기능값에 잘못된 역할을 붙이는 문제가 나왔습니다. 사전 게이트에 따라 전체7문서 평가는 보류했습니다. [결과와 다음 과제](specs/ai-developer/04-analysis-provider/quote-extraction/validation.md)

## Jev 독립 역할·상태 판정

추출 모델의 기존 분류를 제외하고 원문·정확 인용만으로 역할과 상태를 별도 질문하는 합성 실험입니다.
24호출에서 역할21/24, 상태20/24, 동시정답18/24, 순서일관9/12쌍, 잘못된 제품확정3회를 기록했습니다. 사전 게이트 미통과로 실제 추출 흐름에 연결하지 않았습니다. 전체197테스트 통과. [결과와 한계](specs/ai-developer/04-analysis-provider/independent-classification/validation.md)

## 튜닝 실험 종료

마지막 동일사례 비교에서 기존 Jev2축은19/24, 신규4질문은16/24 정답이었습니다. 신규 방식은 오채택0건이지만 정상채택4회도 모두미정으로 남아 통과 기준에 미달했습니다. 계획에 따라 추가 튜닝과 실제 문서 확대를 중단했습니다.

**자동 확정 Profile의 품질은 아직 확보되지 않았습니다.** 전체206코드테스트 통과와 내용 정확도는 별개입니다. [종료 정리 및 확보한 범위](specs/ai-developer/04-analysis-provider/tuning-conclusion.md)
