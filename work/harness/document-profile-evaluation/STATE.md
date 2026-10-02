# Document Profile Evaluation — 준비 후 중단

## 현재 요청

실제 기획 문서 1개로 10개 Profile 필드의 기대값 초안과 문서 입력→새 후보 추출→의미 분류→최종 Profile 평가를 준비한다. 기존 모델 비교 추가 호출은 중단한다.

## 제한

- 새 모델 호출 0회, 서비스 코드 변경 0건, 배포·Spring 연결·큰 goal 재개 없음.
- 기존 후보를 입력에 주입하지 않음. 평가 정답·단어 예외를 모델 입력에 넣지 않음.
- 기존 결과, 다른 작업의 dirty 파일과 큰 goal 중단 상태 유지.

## 확인한 사실과 결정

- AgentFit 기획서 `E:/AgentFit/Docs/project-proposal.md`, SHA-256 `9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451`, 186줄/7,796 code points. 작업 트리의 같은 문서와 바이트 일치.
- 기존 개발 문서이므로 독립 일반화 검증 자료가 아님. 연결된 PRD나 대화의 스택 사실은 포함하지 않음.
- 조사 코드 기준 `16c024954c77c4d7171fb83475221d8a01d150d5`, 준비 브랜치 `feature/document-profile-evaluation-plan`.
- 필드 초안: 명시됨 5, 미정 5, 필드 전체 명시적 없음 0. 부분 기능·권한의 명시적 부정은 별도 기록.
- 기능 초안 16묶음/36개 의미 단위, 비기능 긍정 사실 4개, 문맥 점검 항목 16개.
- 실제 코드의 integrated-nvidia 경로는 semantic_assessment=True. 배포 모드는 미확인이고 기본 코드 모드는 default. 최근 모델 비교 지침이 서비스에 적용됐다고 가정하지 않음.
- 기존 observer만으로 원시 추출·대표 기능 선정의 모든 손실을 구분할 수 없어 향후 관측 보완을 계획함. 이번에 구현하지 않음.

## 변경 파일

`specs/ai-developer/document-profile-evaluation/`의 spec.md, plan.md, expected-values-draft.md, gold-draft.json, expected-profile-draft.json, preparation-validation.json 및 이 STATE.md.

한 번 사용한 로컬 문서 작성 도우미는 `E:/AgentFit/tmp/prepare_document_profile_gold.py`이며 앱·평가 실행 코드는 아니다. Git에는 평가 자료와 상태 파일만 포함한다.

## 검증

- 원문 바이트 해시, 두 위치 문서 일치, 인용 98곳의 Unicode 위치·문자열 일치 확인.
- 기존 `validate_profile`/`check_profile_snapshot`로 기대 Profile 초안의 형식·근거 검증 통과. 의미 정답이 사용자 승인됐다는 뜻은 아님.
- 신규 모델 호출 0회. 실제 추출·분류 품질 수치 없음. 앱 테스트 및 네트워크 모델 평가 미실행(문서 준비만 수행).

## 남은 작업과 중단 지점

1. 사용자가 10개 필드 및 세부 의미 초안을 검토하면 골드 동결.
2. 별도 승인 후 평가 전용 관측·채점 도구 구현과 합성 응답 테스트.
3. 실제 호출은 그때 무료 조건과 별도 호출·시간 상한을 확인하고 허가받은 범위에서만 수행.

현재 상태: **평가 준비 완료, 기대값 초안 검토 대기, 실행하지 않고 종료**.
