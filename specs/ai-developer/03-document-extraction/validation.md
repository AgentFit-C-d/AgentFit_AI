# 문서 추출 검증

## 실행 범위

- Python 3.12 격리 환경에 `pypdf==6.19.0` 설치 후 실제 PDF 객체를 만든 결정적 테스트를 실행했다. 텍스트·Markdown·PDF 10건과 기존 AI 테스트를 포함해 전체 **451건 통과**했다.
- 정상 2쪽 PDF의 페이지 범위, 암호 PDF, 시그니처·구조 손상, 전체 빈 내용, 텍스트/빈 페이지 혼합, 101쪽, 100,000자 초과를 각각 확인했다. TEXT의 Unicode code point 포함 경계와 Markdown UTF-8 strict decode·파일 크기 거부도 확인했다.
- 실제 자식 프로세스를 0.001초 기한으로 실행한 결과 `PDF_TIMEOUT`을 반환했다. `subprocess.run`의 timeout 정리를 사용한다. Worker에 전달하는 환경 키 집합에는 `UPSTAGE_API_KEY`, `NVIDIA_API_KEY`, `OPENAI_API_KEY`가 없음을 확인했다.
- `git diff --check` 통과. 합성 PDF·테스트 결과에서 원문을 파일로 기록하지 않는다.

## 판정과 한계

문서 추출 모듈은 로컬 결정적 검증을 통과했다. FastAPI HTTP 입력·취소·동시성 및 Spring 저장·화면 연동은 미구현이므로 첫 Feature 또는 실사용 완료로 판정하지 않는다. PDF 파서 자체의 메모리 사용은 이 Worker의 15초 기한만으로 제한되지 않는다. 운영 시 프로세스·컨테이너 메모리 제한과 대표 실제 PDF 검증이 필요하다. 이미지 PDF OCR과 PDF의 의미 구조 복원은 지원 범위 밖이다.

`pypdf`의 [텍스트 추출 문서](https://pypdf.readthedocs.io/en/6.19.0/user/extract-text.html)는 이미지에서 텍스트를 읽지 못하며 큰 content stream의 메모리 사용이 커질 수 있다고 설명한다. [PyPI의 6.19.0 릴리스](https://pypi.org/project/pypdf/6.19.0/)를 의존성 버전으로 고정했다.
