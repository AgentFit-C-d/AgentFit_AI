# PDF Worker 메모리 제한 명세

## 목적

악성·비정상 PDF가 `pypdf` 추출 중 과도한 메모리를 사용해 FastAPI 부모 프로세스와 다른 분석 요청을 불안정하게 만드는 일을 막는다. 기존 10 MiB 입력·100쪽·10만 글자·15초 제한과 공개 오류 형식은 유지한다.

## 결정

- PDF Worker는 원본을 표준 입력에서 읽거나 `pypdf`를 import하기 전에 512 MiB 운영체제 메모리 제한을 적용한다. 다른 Worker와 부모 프로세스에는 이 제한을 적용하지 않는다.
- Windows 8 이상은 Worker 자신을 새 Job Object에 등록하고 `JOB_OBJECT_LIMIT_PROCESS_MEMORY`를 512 MiB로 설정한다. 등록 실패 시 PDF를 처리하지 않고 안전한 `PDF_WORKER_FAILED`를 반환한다. Job handle은 Worker가 끝날 때까지 유지한다. 이미 다른 Job에 속해 있으면 Windows의 nested Job 규칙을 따른다.
- Linux는 `resource.RLIMIT_AS`의 soft·hard limit을 512 MiB 이하로 낮춘다. 기존 hard limit이 더 낮으면 그 값을 유지한다. 제한 설정 실패 또는 지원하지 않는 OS는 PDF를 처리하지 않고 `PDF_WORKER_FAILED`로 실패한다.
- 제한 초과로 Python `MemoryError`가 발생하면 `PDF_WORKER_FAILED`만 반환한다. 프로세스가 비정상 종료돼도 부모는 기존처럼 같은 안전 코드로 매핑한다. 원문·추출문·키·시스템 오류 메시지는 HTTP·일반 로그에 넣지 않는다.
- Windows Job Object는 할당된 프로세스의 commit 한도, Linux `RLIMIT_AS`는 주소 공간 한도다. 같은 숫자가 동일한 실제 RAM 사용량을 뜻하지 않는다. Windows는 Job 등록 전에 발생한 작은 인터프리터 초기 할당을 사후 검사하지 않는다.

## 검증

- 실제 Windows PDF Worker에서 작은 PDF 추출이 기존과 같이 성공한다.
- 분리된 테스트 프로세스에서 제한보다 큰 할당이 실패하고 부모 테스트 프로세스는 살아 있는지 확인한다. Windows에서 Job 설정 자체가 성공했는지 직접 조회한다.
- 제한 설정 실패를 주입해 PDF를 읽기 전에 `PDF_WORKER_FAILED`만 반환하는지 검증한다.
- 전체 문서 추출 테스트와 AI 테스트, 로컬 FastAPI PDF 요청을 검증한다. Linux 경로는 Linux 실행 환경에서 같은 제한·할당 테스트가 필요하며 Windows 결과만으로 Linux 검증을 완료했다고 하지 않는다.

## 근거와 제약

[Microsoft Job Object 메모리 제한](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information), [Job 등록 규칙](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject), [Python resource 제한](https://docs.python.org/3.11/library/resource.html)을 따른다. 이 제한은 PDF Worker에만 적용된다. 요청 전체 프로세스, 배포 컨테이너, 호스트 자원의 종합 상한은 별도 운영 설정이 필요하다.
