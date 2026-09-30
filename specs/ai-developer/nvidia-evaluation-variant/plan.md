# NVIDIA 단독 평가 버전 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. 직접 순차 구현, 독립 최종 리뷰1회. 사용자의 목표 내 자율 설계/계획/구현 승인 적용.

**Goal:** 고정 공개 자료를 NVIDIA 단독 서비스로 평가할 별도 실행 경계를 준비한다.
**Architecture:** 신규 inputs의 strict freeze/무료확인→신규 runner의 preflight/live 분기→기존 단독 서비스 자식→기존 점수/체크포인트 재사용. 기존 baseline 코드와 결과는 유지한다.
**Tech Stack:** Python3.13/unittest/기존 LangExtract/FastAPI 런타임, 추가 의존성 없음.
**Spec:** specs/ai-developer/nvidia-evaluation-variant/spec.md

## Global Constraints

- feature/nvidia-evaluation-variant, base f0d57dd83400c2b692b051f21edc88b425623597. 원래 analysis-runtime 기준선/workspace 보존.
- PUBLIC10문서×3회, 요청1800초/64호출/재시도0. 신규 설정은 DeepSeek 추출·분류·기능/GLM검토. 기존 scorer/기본서비스/평가6모듈 변경 없음.
- 작업45분 점검/suite180초/합성 요청30초·기한10초/실제API0/유료0/운영배포0. 실제 계정 무료 한도/Spring/사람 검토 미확인.

## Review Focus

1. preflight나 잘못된 무료확인으로 키/모델에 접근하는가 — 기본은 입력 검증만, 실제 요청 전 재검증과 누적64회 예약을 검사한다.
2. 다른 실험 결과를 재사용하거나 중단된 요청을 자동 재호출하는가 — 별도 manifest와 immutable checkpoint/started-only 거부를 검사한다.
3. freeze에서 파일 추가·자료 변경·채점기 변경이 빠지는가 — 전체 파일 집합/해시와 동일 corpus/gold 검증을 검사한다.
4. 429/503·권한 오류 후 다음 문서를 호출하는가 — 실패 row 보존 후 영구 중단하고 재실행에서도 새 호출이 없는지 검사한다.
5. 실제 자식 취소·오류에서 원문/키가 기록되거나 분모가 줄어드는가 — 기존 프로세스 경계의 실제 통신/기한/정리와 strict score를 검사한다.

### Task 1: 고정 입력부터 단독 평가·체크포인트까지 구현

**Files:** Create ai_service/agentfit_ai/nvidia_evaluation_inputs.py, nvidia_evaluation_runner.py; Create tests/test_nvidia_evaluation.py와 합성 fixture; Create runtime_tests/test_nvidia_evaluation_runtime.py; Create specfolder/freeze.json, validation.md, review.md, work/harness/nvidia-evaluation-variant/STATE.md; Modify README.md.
**Interfaces:** inputs `prepare_evaluation(corpus_file,gold_file,freeze_file)->dict` returns cases/metadata/paths; `load_nvidia_key(env_file)->str`; `validate_free_access(path,*,reserved_calls,now=None)->dict`; `build_freeze(corpus_file,gold_file)->dict` is offline and does not write. runner `run_scored_process(document,document_id,gold,nvidia_key,*,timeout_seconds=1800,command=None)->score`; `evaluate(prepared,output,nvidia_key,access_file)->summary`; `main(argv=None)->int`. Private `_refresh` verifies new preflight, old pure checkpoint helpers reused.

- [ ] Step1: write tests for preflight10docs/freeze drift, free access expiry/type/endpoint/models/budget, single key, default CLI no key/provider. Run `python -m unittest discover -s tests -p test_nvidia_evaluation.py`. Expected: explicit missing module assertion RED. Implement inputs then focused GREEN.
- [ ] Step2: add tests for30typed rows/replay0/started-only/mismatched output/source drift,429/503 stop+resume stop/reservation cap/expiry and safe failed scores. Expected: runner missing RED. Implement runner with existing process/scorer/checkpoint functions. GREEN including old independent evaluator tests.
- [ ] Step3: real SDK/loopback child tests for10matched/no secrets, malformed/429 singlecall, timeout and cancellation reap. Run new runtime file. Expected: old service shim suffices; all pass with external0, do not replace model boundary with fake pipeline.
- [ ] Step4: generate one new freeze only after code is fixed; run real corpus preflight without env/live, record exact207gold/no quality claim. Write README usage and validation/STATE. Full4suite gate/commit/task-done. Expected: baseline results byte-identical and no new actual run.
- [ ] Step5: final reviewer1→important fixes RED/GREEN1pass→feature push/CI exactSHA. Keep SDD/worktree. Expected: complete evaluator readiness, actual quality/free quota/Spring still unverified.

## 자기 검토

한 Task가 입력부터 저장/재개까지 같은 계약을 소유한다. 기존 API/채점기 파일은 수정하지 않고 소규모 실행 루프만 별도로 둔다. 실제 실행 권한을 합성 테스트에서 얻었다고 간주하지 않는다.
