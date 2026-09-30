# 문서 입력 통합 검증 결과

## 대상 실행

2026-10-01 KST, Windows, 기존 analysis-runtime의 Python 환경을 읽기 전용으로 사용.
`python -m unittest discover -s core_flow_tests -p test_document_input_runtime.py -v`

- **3 tests / 11.996초 / exit 0**.
- Markdown: BOM 포함47bytes·BOM 제거29문자·CRLF·한글·이모지, frontend [17,22), features [24,29).
- PDF: 실제 pypdf 자식 프로세스의 두 페이지 추출, frontend [8,13), features [14,26).
- 모두 DRAFT 이후 사용자가 frontend를 변경해 USER/근거[]로 저장. 유지한 기능은 DOCUMENT 근거를 보존. 재조회·중복409·삭제 검증.
- 잘못된 UTF-8, 빈 Markdown, 100,001자, 손상/암호화/빈/부분 빈/101쪽 PDF의 8종 거절. 기존 초안·확정 값·버전 보존, 추가 분석 프로세스·모델 요청 0, 명시적 재입력 복구.
- 전체 원문·합성 API 키·실패 원문 sentinel이 공개 오류·mock 메모리 상태에 없는지 검사.

제품 코드 변경 없이 기존 동작을 확인했다. 초기3건 통과는 제품 결함 수정의 RED→GREEN 결과가 아니다.

## 전체 검사와 최종 리뷰

최초 전체 검사: unit 1,146통과/5skip(70.333초), runtime23통과(94.427초), contract36통과(9.209초), core8통과(39.700초). 총 **1,213통과/5skip**.

단일 최종 독립 리뷰에서 테스트 허점1건을 확인했다. JSON 상태와 원문을 비교할 때 줄바꿈 이스케이프가 달라 성공 원문 저장을 놓쳤다. 합성 누출 주입으로 감지 실패를 재현한 뒤 검색 문자열 인코딩을 수정했다. 같은 실험이 이제 누출을 감지하며 정상 대상3건도 12.667초에 통과했다. 제품 코드 변경은 없다. [리뷰 및 판단 기록](review.md)에 자세히 남겼다.

수정 후 네 suite도 각각 exit0: unit 1,146통과/5skip **70.834초**, runtime23통과 **95.071초**, contract36통과 **9.835초**, core8통과 **42.849초**. 최종 **1,213통과/5skip**. 기존 `<prefix>`·asyncio 느린 작업 경고와 오류 입력 시험의 CLI stderr가 있었으나 실패한 시험은 없다.

## 남은 범위

- feature/document-input-runtime push/정확한 SHA CI 결과는 작업 상태와 SDD ledger에 기록한다.
- PDF pageCount/characterCount는 mock에서 null. 측정 값 전달 계약은 구현하지 않았다.
- 합성 loopback 제공자만 사용했으며 이번 작업의 추가 외부 모델 호출/유료 사용/배포는 0.
- 별도 실제 평가는 첫 요청 PROVIDER_UNAVAILABLE로1/30 종료 후 중단했다. 사람 gold 검토, 모델 품질, 실제 Spring·DB, 복잡한 PDF/OCR, 운영 로그·백업 삭제는 미검증.
- Python 실행 시 기존 `<prefix>` 경고가 있었지만 세 시험은 정상 종료했다.
