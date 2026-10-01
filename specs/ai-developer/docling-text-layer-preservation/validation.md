# 텍스트 영역 보존 검증 — 2026-10-01

## 변경과 범위

선택형 Docling 변환기의 내보내기/순회를 같은 5개 텍스트 영역으로 명시했다. Docling에 저장된 텍스트 객체가 순회에서 빠지면 `PDF_PARTIAL_TEXT`로 거절한다. 머리말·꼬리말에도 기존 텍스트 포함·반복 횟수·단일 페이지 근거 검증을 적용한다.

Docling JSON에 남은 정보의 유실을 줄이는 수정이다. OCR 오인식 및 Docling 구조 생성 이전 누락을 해결했다는 주장은 하지 않는다. 기본 HTTP 입력기·Profile·모델 선택은 유지된다. 모델 API0회, 추가 다운로드0회.

## 실행 근거

| 검증 | 결과 |
|---|---|
| 수정 전 기준 관련 테스트 | 9개 실행, 7통과·SDK미설치2skip |
| 새 회귀 테스트 RED | 기존 코드에서 누락/잘못된 수락으로 assertion7개 실패 |
| 실제 DoclingDocument RED | 머리말 누락으로 1개 실패 |
| 수정 후 SDK미설치 환경 | 15개 실행, 12통과·3skip |
| 실제 SDK·PDF·추출 평가 관련 테스트 | **39개 모두 통과**, 30.732초 |
| 전체 unittest | **1,252개 실행, 1,245통과·7skip**, 75.688초 |
| 고정 mixed JSON 재생 | 머리말1회 복구·페이지 문자 위치 통과 |
| 원문/기존 평가 보존 | 원문10·검토문/대응10·이전JSON174·gold해시 불변 |

전체 테스트는 analysis-runtime Python에서 `python -m unittest discover -s tests -q`로 실행했다. 관련 SDK 테스트는 grounding-venv Python에서 `tests.test_docling_structured_trial`, `tests.test_docling_grounding_evaluation`, `tests.test_docling_pdf_comparison`, `tests.test_full_candidate_grounding_evaluation`을 실행했다. 상한은 각각900초/300초, 자동재시도0이었다.

SDK 테스트 자체는 exit0이었다. 부모 실행기의 콘솔 출력만 cp949가 진행률 문자를 인코딩하지 못해 exit1이 됐다. UTF-8 저장 로그와 자식 종료 기록을 직접 확인해 테스트 결과와 구분했다. 테스트를 재실행해 덮어쓰지 않았다.

## 회귀 범위

- body/furniture/background/invisible/notes의 텍스트 보존.
- 머리말만 있는 페이지와 Unicode/emoji 문자 위치.
- 같은 본문/머리말 문장의 중복 횟수 검사.
- 순회되지 않은 텍스트, 알 수 없는 영역의 누락, 잘못된 페이지 근거 거절.
- 실제 DoclingDocument의 머리말·본문·꼬리말과 기존 표/제목 PDF 통합 확인.

## 고정 결과 재생과 제한

이전 OCR 결과 JSON을 그대로 로드해 변환 어댑터만 재실행했다. `Native metadata: Project Birch`가 출력에 한 번 나타나며 전체213자, 표1개, 페이지 범위가 일치했다. 원본 JSON/PDF 해시는 `replay.json`에 기록했다.

`FastAP!` 오인식과 `도입하지 않음` 누락은 남아 있고, 이전 OCR 품질 판정0/2는 유지된다. 사람 검토 및 모델 평가 허용도 false다. 숨김/주석까지 포함된 원문 텍스트를 제품 기능의 확정 근거로 자동 취급하면 안 된다.

독립 리뷰 및 Git 전달 상태는 STATE.md에 기록한다. 실제 Spring 저장·운영 배포·새 문서 일반화 검증은 미완료다.
