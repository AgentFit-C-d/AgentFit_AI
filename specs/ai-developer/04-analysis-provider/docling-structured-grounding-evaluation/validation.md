# Docling 구조 문서·근거 결합 평가

## 재현 범위

- 실험 전용 venv에 Docling 2.130.0, LangExtract 1.7.0, pypdf 6.19.0, ReportLab 5.0.1을 설치했다. 기본 FastAPI 의존성·PDF worker는 변경하지 않았다. 표준 Docling은 로컬에서 처리했으며 처음 실행 때 공개 모델 자산을 내려받았다. 실제 PDF를 외부 문서 처리 API나 LLM에 보내지 않았다.
- 기존 튜닝 18건과 다른 고정 합성 12건(반복·부정·검토안 각 4건)을 `heldout-cases.json`에 작성했다. 최초 모델 호출 전 SHA-256 `827bcd481eb4a5b8963c60e0961ae40df18dfacf400b77ac0d6b7348ba862a1e`로 고정했다. 12건 모두 한글 합성 PDF로 생성한 뒤 Docling 정규 텍스트에서 정확한 고유 문맥과 한 페이지의 골드 위치를 찾았다.
- 같은 합성 PDF를 공유하는 사례는 한 번 변환·추출했다. 한 실행에서 PDF 9개, 모델 호출 9회다. 실제 PDF 경로와 원문·인용·응답·키는 안전 결과에 기록하지 않았다.

## 관측 결과

| 합성 PDF 입력 경로 | 완료/12 | 오확정 | 허용 누락 | 골드 근거 위치 일치 |
| --- | ---: | ---: | ---: | ---: |
| 기존 pypdf | 12 | 0 | 0 | 12 |
| Docling native | 12 | 0 | 0 | 12 |
| 표준 Docling + LangExtract + 규칙 | 12 | 0 | 0 | 12 |

- 표준 경로의 범주별 판단은 반복·부정·검토안 각각 `allow` 2건, `review` 2건이었다. 세 입력 경로를 각각 라이브 호출했으므로 모델 출력 변동이 섞일 수 있다. 짧은 합성 PDF에서 표준 Docling의 정확도 향상은 관측되지 않았다.
- 별도의 표·제목 합성 PDF는 표준 Docling에서 제목 1개와 표 1개를 식별했고 모든 셀 문자열이 정규 텍스트에 포함됐다. 표준 경로의 결과에 제목·표가 누락되거나 같은 본문 항목이 한 번으로 합쳐지면 전체 문서를 보류하는 테스트를 추가했다.
- 로컬 실제 PDF 1건(1쪽)은 `pypdf`/native 각 1,630자, 표준 Docling 2,020자·제목 6개·표 2개였다. pypdf 토큰 중 표준 텍스트에서 찾은 비율은 0.9554다. 문자 수나 이 비율만으로 추출 품질의 우열을 판단하지 않는다.
- 별도 프로세스에서 같은 실제 PDF의 표준 Docling cold 실행은 약 19.6초, 표본화한 프로세스·자식 프로세스 최고 RSS 약 1,018MiB였다. 현행 PDF worker의 15초·512MiB 제한을 넘는다. 샘플링 메모리 수치는 운영 환경 최대 사용량의 상한을 증명하지 않는다.

## 판정과 남은 검증

- 위 표의 12건은 기존 18건을 사용해 수정하지 않은 새로운 합성셋이지만, 현재 규칙을 아는 개발자가 작성했다. 독립 실제 문서 일반화 근거가 아니다. **위 점수는 골드 필드와 `present` 상태를 규칙에 제공한 조건부 근거 평가**이며 모델의 필드·상태 분류 정확도를 측정하지 않았다. 아래 보강 평가에서 이를 분리했다.
- 표·제목이 있는 긴 PDF의 근거 판단 골드, 스캔 PDF/OCR, 다중 페이지 표, 실제 Profile 출력, Spring 연동은 미검증이다. 표준 Docling은 현재 worker에 바로 승격할 수 없다. 별도 메모리·시간 예산의 비동기 처리 경로를 설계·검증해야 한다.
- 안전 결과 파일은 `E:/AgentFit/tmp/docling-grounding-heldout-20260929-v1.json`, `E:/AgentFit/tmp/pypdf-grounding-heldout-20260929-v1.json`, `E:/AgentFit/tmp/native-grounding-heldout-20260929-v1.json`이다. pypdf 첫 결과의 진단 필드 `docling_calls`는 명칭 오류이므로 입력 경로별 호출 수 비교에 사용하지 않는다. 이후 CLI는 `input_conversions`로 수정됐다.

## 2026-09-30 독립 리뷰 후 보강 결과

- 표 셀 문자열만 남고 행·열 관계가 무너진 문서를 허용하던 결함을 실패 테스트로 재현했다. Docling `TableItem.export_to_markdown`의 전체 구조가 같은 페이지 본문에 연속해서 있어야 통과하도록 바꿨다. 실제 표·제목 합성 PDF와 로컬 실제 PDF 1건(제목 6개·표 2개)이 강화한 검증을 통과했다. 실제 PDF는 LLM에 전송하지 않았다.
- `structured-cases.json`의 합성 표 PDF 1개·4사례를 모델 호출 전 SHA-256 `116501e9c7987fd583b98c4b9c7a9536d6147e4727b5e613b68b2a8937253d97`로 고정했다. Git의 Windows/Linux 줄바꿈 차이만 LF로 정규화해 해시를 확인한다. Docling에서 제목 1개·표 1개와 네 근거의 단일 페이지 고유 위치를 확인했다.
- LangExtract 후보 뒤 Solar가 **골드 없이** 필드와 `confirmed/negated/tentative/irrelevant` 상태를 분류한다. 규칙은 모델 분류와 실제 근거 위치를 사용한다. 골드는 마지막 채점에만 쓴다. 후보 한 건의 필드가 틀린 자동 허용은 오확정과 허용 누락을 함께 기록한다.

| 모델 자체 분류를 포함한 합성 평가 | 완료 | 오확정 | 허용 누락 | 정확 근거 |
| --- | ---: | ---: | ---: | ---: |
| 반복·부정·검토안 12건, 표준 Docling | 12/12 | 0 | 1 | 12/12 |
| 표·제목 4건, 표준 Docling | 4/4 | 0 | 0 | 4/4 |
| 같은 표·제목 4건, Docling native | 4/4 | 0 | 2 | 4/4 |
| 같은 표·제목 4건, pypdf | 4/4 | 0 | 2 | 4/4 |

- 12건의 누락은 N04에서 발생했다. 근거 위치와 `confirmed` 상태는 맞았지만 모델이 `database` 필드로 분류하지 못했다. 현 결과만으로 필드 오류 원인을 더 세분화할 수 없다. 표 사례 비교도 각 경로에서 모델을 별도로 호출했으므로 표준 Docling의 일반적 우위를 증명하지 않는다.
- 안전 결과는 `E:/AgentFit/tmp/docling-plain-classified-20260930-v1.json`, `E:/AgentFit/tmp/docling-structured-classified-20260930-v1.json`, `E:/AgentFit/tmp/native-structured-classified-20260930-v1.json`, `E:/AgentFit/tmp/pypdf-structured-classified-20260930-v1.json`에 있다. 원문·후보·키·모델 응답은 기록하지 않았다.
- 이 평가는 각 사례의 목표 후보를 채점한다. 추가 추출 후보가 실제 Profile에 들어갔을 때의 오확정, 장문·스캔 PDF, 새 실제 문서 일반화, Spring 연동, worker의 15초·512MiB 한도는 여전히 미검증이다. 표준 Docling의 이전 cold 실행은 약 19.6초·표본 RSS 약 1,018MiB여서 기본 PDF worker에는 연결하지 않았다.
- 로컬 서비스 전체 테스트 771건 통과(선택 의존성 5건 건너뜀), 실험 venv의 Docling 실제 PDF 포함 23건 통과. 커밋 `ebbf7ec`의 [Linux CI 실행](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36588967898)도 통과했다. 이 CI는 기본 서비스 의존성만 설치하므로 선택형 Docling 실제 변환 테스트는 로컬 실험 venv에서 확인했다.
