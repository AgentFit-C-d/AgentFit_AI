# 로컬 OCR 변환 실험 상태

- 목표 active. 직전 goal turn은 progress: 모델 비교 종료 확정, 새 문서 입력 누락 재현, 개인정보 제거 검토문 작성,203ed11/80ad6ae push 및CI36811826870 success.
- 현재 linked worktree E:/AgentFit/tmp/worktrees/document-input-runtime 재사용. feature/local-ocr-document-preparation,기준80ad6ae. 사용자 SDD·자율 실행·feature push 승인 유지. 기존.superpowers와원문/평가파일보존.
- 이번은 가능성 검증(spike): 제품 모듈을 작성하지 않고 설치된 Docling/RapidOCR를 로컬 실행. 임시 코드와 결과는 scratch/output에 보존. spec/plan 작성. 모델API0,새원문외부전송0.
- 기준 테스트 session7072 terminal exit0: Docling 관련 9건 통과(35.910초). 재실행하지 않는다.
- 설치 환경: grounding-venv Docling2.130.0/docling-core2.99.0/RapidOCR3.9.2/Torch2.14.0. 한국어 Torch PP-OCRv4 고정 모델/사전 4파일을 준비하고 해시 확인했다. 모델 API 0회.
- 합성 v1은 6.401초 후 TypeError로 종료했다. 라이브러리 ParseParams.update_batch가 ocr_version/model_type Enum을 요구하지만 실험 코드가 문자열을 넘긴 것이 확인됐다. OCR 품질 결과가 아니다. 처음 코드와 결과를 synthetic-v1에 보존한다.
- 2026-10-01 04:03 UTC 재개: 직전 진행률 보고는 no progress로 분류. Git/파일/terminal 결과를 대조했고 계획의 설정 수정 1회로 Enum 자료형을 적용한다. synthetic-v2에서 같은 문서/모델을 검증하며 추가 자동 재시도는 없다.
- 합성 v2 session16877 terminal exit0. 변환2/2 종료(13.048/13.111초), audit 품질0/2·표0/6·부정 표현누락2/2. page/bbox는 유효하지만 의미를 보장하지 않음. 반복은 공백/마침표 손실. 초기 실패+설정 수정1회 상한 종료. 실제 PDF/DOCX 그림 OCR 미실행.
- 네이티브 문장은 JSON의 furniture/page_header에 남지만 기본 export/iterate에서 제외됨. 캐시 JSON을 전체 layer로 export하면 복구됨. OCR 오인식 원인은 추가 조사 필요. 구형 RapidAI 데모의 height32를 현 모델에 적용해야 한다는 근거 부족으로 추가 실행하지 않음.
- 독립적인 DOCX 구조 추출0.047초: text nodes621, tables13, images9, media9, 본문/헤더/푸터3parts. 순서·표 병합·그림 참조 검증. 원본/개인정보검수전 산출물 로컬 전용. 모델평가허용false/사람검토false. 번들 LibreOffice없어 전체페이지렌더링미실행. DOCX기본입력지원추가아님.
- .superpowers/experiments/local-ocr-document-preparation/verify_spike.py를 번들Python에서 실행: 결과/코드/원문해시 일치, native기준 image-only0자/mixed31자, 표네이티브누락확인, 품질실패유지. 별도 기존verify_inspection_artifacts.py: 원문10·검토문/대응10·이전JSON174·gold불변확인. 첫analysis-runtime실행은pdfplumber없어미실행, 번들런타임으로검증성공.
- 이번 goal turn은 progress: 품질실패를 계측했고 기본export누락원인과Docx구조자료를 확보했다. 활성모델/변환세션없음. 전체목표active, 실제Spring/운영/새문서사람정답/10×3품질검증은미완료. 추정진행도60~65%유지.
- Git: 명세/계획/validation/안전한audit2개/STATE를 4e70745로 commit했고 feature/local-ocr-document-preparation 원격 push exit0 및 upstream 설정을 확인했다. 원문/모델/scratch는 stage하지 않았다. 이 상태 기록만 후속 commit한다.
- 다음: 원문 텍스트 영역이 숨겨지는 오류의 SDD 회귀 보완(전체 content layer 및 native/converted 누락 대조), OCR은 검출 crop과인식/전처리를 분리조사한뒤새조건등록. 실패한설정으로실제문서를계속돌리지않음. 새기획서정답/사람검토를최종통과로간주하지않음.
