# 기능 관계 회귀 평가 실행

평가 대상은 대표 기능과 구성 기능 사이의 포함 관계다. 정답 근거 위치와 확정/부정/검토 상태를 입력으로 공급한다. 후보 추출·분류·대표 생성 정확도나 전체 서비스 준비도를 측정하지 않는다.

`cases.json`의 창작 12사례를 기본 2순서 × 2회씩 평가한다. 원문·ID·위치는 유지하고 후보 배열만 뒤집는다. 기존 제품 `review_feature_relations`를 사용하며 모델에 정답을 전달하지 않는다. 첫 실제 평가 전 동결한 코퍼스 SHA-256을 명시해야 한다(CRLF→LF 정규화 바이트).

## 실행

`ai_service`에서 프로젝트 Python 환경으로 실행한다. 아래 `CORPUS_SHA256`는 동결본의 실제 해시로 바꾼다.

```powershell
rtk proxy python -m agentfit_ai.feature_relation_evaluation --preflight --corpus-sha256 CORPUS_SHA256
rtk proxy python -m agentfit_ai.feature_relation_evaluation --live --corpus-sha256 CORPUS_SHA256 --env-file E:/AgentFit/.env --output E:/AgentFit/tmp/feature-relations-new-run.json
```

- preflight는 키 조회·외부 API 호출·결과 파일 생성을 하지 않는다.
- `--live`에서만 API를 호출한다. 출력 파일은 아직 존재하지 않아야 하고 부모 폴더는 존재해야 한다. 기존 결과는 덮어쓰지 않는다.
- 기본 모델은 DeepSeek V4.1 Flash. `--model`로 기존 NVIDIA 어댑터의 GLM 5.3 또는 Kimi K3를 선택할 수 있다.
- `--repeats`는1~3(기본2). 기본48호출, 자동 재시도0. 한 호출 제한600초/출력8192토큰은 기존 helper 설정이다.
- 보고서에는 ID·판정·개수·코드/코퍼스 해시·제한된 공급자 메타데이터만 저장한다. 키·문서·인용·응답 전문은 저장하지 않는다.
- 최초와 매 호출 후 checkpoint를 저장한다. 같은 폴더의 임시 파일에 기록을 마친 뒤 원자적으로 교체하므로 부분 쓰기 실패에도 직전 checkpoint를 보존한다. 저장 실패 시 추가 호출은 하지 않는다. 중단 결과의 `planned`는 전체 계획 분모를 유지한다. 관측 시간이 끝났다는 이유로 같은 실행을 재시작하지 않는다.

## 해석

`matched`는 지정 정답과의 일치, `false_covered`는 오포함, `false_uncovered`는 오거절이다. `uncertain`과 `failed`도 계획 분모에 포함한다. `completed`는 처리된 행수여서 실패 행도 포함하며 성공 횟수를 뜻하지 않는다.

순서·반복 일관성은 **확정 응답**이 모두 같을 때만 성공이다. uncertain끼리 또는 failed끼리 같아도 성공으로 세지 않는다. repeats=1이면 반복 일관성의 평가 분모는0이다.

모든 계획 행이 정답과 일치하고 실행 전후 코드 해시가 같아야 `gate_passed=true` 및 종료0이다. 진행 중 checkpoint는 최종 검증 전이므로 항상 `gate_passed=false`다. 정상 실행이 끝나도 회귀 미달이면 종료1, 설정 오류는 종료2다. 종료1의 `state=finished`는 평가 실행 종료를 뜻하며 품질 통과를 뜻하지 않는다.

합성 회귀 통과는 실제 문서 검증·추출/분류 품질·사용자 확인/저장 통합 검증을 대체하지 않는다. 결과를 확인한 이 사례들은 이후 개발 회귀 세트이며 독립 최종 검증 문서가 아니다.
