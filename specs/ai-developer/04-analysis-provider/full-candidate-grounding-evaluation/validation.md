# 전체 후보 근거 평가 결과

## 범위와 고정

- 새 합성 PDF 4개(반복·부정·검토안·표 각 1개), 자동 허용해야 할 정확한 근거 5개를 `cases.json`에 표시했다. 첫 모델 호출 전에 LF 기준 SHA-256 `d6bf2dfbdf02fbd1a3892a834cd72a4d64eaf867c7b92459c768fa04021b4e99`로 고정했다. 실제 Docling 변환 뒤 5개 모두 단일 페이지의 고유 구간이었다.
- LangExtract의 **모든** 후보와 별도 Solar 필드·상태 분류 결과를 규칙에 넣는다. `(근거 구간, 필드)`가 골드에 없는 자동 허용은 오확정이고, 골드가 허용되지 않으면 누락이다. 모델은 골드를 받지 않는다.
- 실제 PDF는 이 평가에서 LLM으로 전송하지 않았다. 결과 파일에는 원문·인용·키·모델 응답을 저장하지 않았다.

## 관측

| 입력 경로와 분류 지시문 | 실행 | 추출 후보 | 허용/골드 5개 | 오확정 | 누락 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 표준 Docling, 기존 지시문 | 1 | 10 | 4/5 | 0 | 1 |
| 표준 Docling, 기존 지시문 | 2 | 10 | 4/5 | 2 | 3 |
| 표준 Docling, 필드 정의 추가 | 1 | 10 | 5/5 | 0 | 0 |
| 표준 Docling, 필드 정의 추가 | 2 | 10 | 5/5 | 0 | 0 |
| pypdf, 필드 정의 추가 | 1 | 12 | 3/5 | 0 | 2 |
| Docling native, 필드 정의 추가 | 1 | 12 | 3/5 | 0 | 2 |

- 기존 지시문에서 같은 표 문서·같은 4개 후보를 세 번 분류하자 필드가 `features` 1회, `database` 2회로 문서 전체에서 뒤집혔다. 일반 필드 정의만 추가한 임시 호출에서는 같은 표 3회가 모두 `features`였고, 별도 DB·기능 혼합 합성 문서 3회에서 각각 `database`·`features`였다. 관측은 프롬프트 모호성이 주된 원인이라는 가설을 지지하지만 모델의 장기 안정성을 증명하지 않는다.
- 기존 지시문 2회차의 누락 3개는 모두 필드 불일치였다. 네 문서는 원인 조사와 지시문 변경에 사용돼 독립 최종 검증셋이 아니다. 입력 경로별 모델 호출도 각각 달라서 표준 Docling의 일반적 우위를 단정할 수 없다.
- 안전 수치 파일: `E:/AgentFit/tmp/full-candidate-docling-20260930-v1.json`, `E:/AgentFit/tmp/full-candidate-docling-20260930-v2.json`, `E:/AgentFit/tmp/full-candidate-docling-field-defined-20260930-v1.json`, `E:/AgentFit/tmp/full-candidate-docling-field-defined-20260930-v2.json`, `E:/AgentFit/tmp/full-candidate-pypdf-field-defined-20260930-v1.json`, `E:/AgentFit/tmp/full-candidate-native-field-defined-20260930-v1.json`.

## 실서비스 판정

아직 승격하지 않는다. 네 합성 문서의 두 필드만 다뤘고 새 실제 문서 골드, 전체 Profile 필드, 추가 후보의 값 정규화·중복 합치기, Spring 연동, 장문·스캔 PDF 및 Docling worker 한도는 검증되지 않았다. 표준 Docling cold 실행은 이전 측정에서 약 19.6초·RSS 약 1,018MiB로 현재 PDF worker 15초·512MiB를 초과했다.

로컬 서비스 전체 테스트와 실험 venv의 실제 Docling 포함 30건이 통과했다. 커밋 `1244f46`의 [Linux CI](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36592426230)도 통과했다. CI는 기본 서비스 의존성만 설치하므로 실제 Docling 변환 테스트는 로컬 실험 환경 결과다.
