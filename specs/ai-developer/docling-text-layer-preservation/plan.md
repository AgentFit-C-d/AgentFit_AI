# Docling 텍스트 영역 보존 구현 계획

> 직접 실행: superpowers:executing-plans 및 test-driven-development. 사용자 자율 승인을 적용한다.

**Goal:** 레이아웃 영역에 따른 텍스트 누락을 복구하거나 안전한 실패로 드러낸다.
**Architecture:** 기존 선택형 변환기의 export/iterate 범위를 맞추고 텍스트 목록을 대조한다. 서비스 경계는 유지한다.
**Tech Stack:** Python unittest, 선택형 Docling2.130.0/docling-core2.99.0.
**Spec:** specs/ai-developer/docling-text-layer-preservation/spec.md

## 실행 상한

- 실제 모델 API0·다운로드0·외부 문서 전송0·자동 재시도0.
- 단위 RED/GREEN 각120초, 관련 Docling 통합 검증300초, 전체 unittest900초, 캐시 재생120초.
- 독립 리뷰1회 최대600초. 관측된 코드 결함 수정 뒤 관련 테스트 재실행만 허용한다. 임의 모델 튜닝은 없다.
- `feature/docling-text-layer-preservation`을 현재 linked worktree에서 사용한다. 원문/기존 결과/scratch 보존.

## Review Focus

- 머리말만 있는 페이지도 원문 위치와 함께 보존되는가?
- 같은 문장이 본문과 머리말에 반복돼도 한 번으로 축약되지 않는가?
- furniture 루트나 연결 끊긴 객체 등 순회에서 제외된 텍스트가 조용히 통과하지 않는가?
- 머리말/주석의 잘못된 페이지 근거 및 표 구조 누락이 계속 거절되는가?
- 선택형 SDK 미설치 환경과 실제 Docling SDK에서 동일한 계약을 지키는가?

## Task 1: 전체 텍스트 영역 보존과 누락 검증

**Files:** ai_service/agentfit_ai/docling_structured_trial.py, ai_service/tests/test_docling_structured_trial.py, 이 명세 폴더 및 work/harness/docling-text-layer-preservation/STATE.md.
**Interfaces:** 기존 convert_structured_pdf_bytes(raw: bytes, *, converter=None) -> StructuredDocument 및 오류 계약 유지. 레이어 선택 문자열은 SDK의 문자열 Enum과 호환되며 강제 SDK import를 추가하지 않는다.

- [x] RED: body/furniture/background/invisible/notes 및 반복·잘못된 페이지·미연결 텍스트 회귀 테스트를 먼저 작성한다. 기존 출력 누락 및 미연결 객체 수락으로 실패해야 한다.
- [x] GREEN: export/iterate 모두 명시적인 같은 레이어 집합을 전달하고 document.texts의 모든 객체가 순회됐는지 확인한다. 기존 검증은 유지한다.
- [x] 선택형 Docling SDK의 실제 DoclingDocument와 기존 PDF 변환 테스트를 실행한다. 모든 관련 테스트 통과가 기대 결과다.
- [x] 고정 mixed JSON을 새 추론 없이 재생한다. 머리말 보존과 페이지 offset을 확인하고 기존 OCR 오인식이 여전히 남는지 별도로 기록한다.
- [x] 전체 unittest를 실행하고 실패/skip을 분리 기록한다. 제품 모듈 영향 범위 검증 후 기존 자료 보존과 diff를 확인한다.
- [ ] 독립 리뷰1회 및 필요 시 회귀 검증으로 수정한다. 명시적으로 변경 파일만 commit/push한다.
