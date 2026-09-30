# 독립 Profile 평가 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자 지정 직접 순차 구현, 목표 내 자율 실행 권한을 유지한다.

**Goal:** 사전 고정된 새 공개 문서와 골드로 실제 통합 서비스의 누락·잘못된 제안·미채점 항목을 분리해 측정한다.
**Architecture:** frozen code/config + source/gold registry → strict source-position scorer → request-owned integrated worker → typed per-run checkpoints/summary.
**Tech Stack:** Python3.13/unittest, existing LangExtract1.7.0 and analysis_process, standard library.
**Spec:** specs/ai-developer/04-analysis-provider/independent-profile-evaluation/spec.md

## Global Constraints

- base9af3f2a,feature/independent-profile-evaluation; productionpipeline unchanged. UTF8/100000bytes/100000codepoints,1800seconds,10families×3runs. Defaultmodels/settings frozen before source reading.
- No source/quote/Profile/raw/modelreasoning/key/exceptiontext in Git or result. Typed positions/IDs/hashes/counts only. No implicit output semantic acceptance; unassessed stays visible; releasegate alwaysfalse until independenthuman+fullrequirements.
- Existing previous gate1068pass/5skip/runtime9pass/exactCI36712248884. Taskcompletion gate alltests/runtime_tests.

## Review Focus

1. 예약metadata의seen=false가이미노출된계열/해시보다우선하지않는가;내용변형/중복/경로변조가독립표본으로통과하지않는가.
2. 같은인용의반복등장·복합값·여러골드단위가포함된범위가매칭수나precision을부풀리지않는가.
3. 실패·부분실행·unassessed·모든null·명시적부재가분모/전체품질에서사라지지않는가.
4. 중단/기한/기존checkpoint/해시변경에서API중복호출·원문/키로그·조용한결과덮어쓰기가없는가.
5. 공개README자동일치결과가사람골드/수정부담/한국어기획서/실사용완료인것처럼표현되지않는가.

### Task 1: 사전 고정·자료 적합성과 근거 위치 채점

**Files:** Create agentfit_ai/independent_profile_evaluation.py, tests/test_independent_profile_evaluation.py, specfolder/freeze.json and corpus.json; local-only source/gold under E:/AgentFit/output/independent-profile-v1.
**Interfaces:** `verify_corpus(cases: list[dict], prior: list[dict], root: Path)->list[dict]`; `validate_gold(document: str, gold: dict)->dict`; `score_confirmation(document: str, document_id: str, gold: dict, outcome: dict)->dict`. Exact wire/gold/score shapes and precedence are fixed in spec's 구현 전 확정 계약. Split source/gold validators into `agentfit_ai/independent_evaluation_corpus.py` to keep scoring separate; re-export verify_corpus/validate_gold from independent_profile_evaluation.

- [x] Step 1: Freeze existing source/config before reading corpus. Verify old10sourcehashes,excludePUBLIC04/05,acquireofficialcommit-pinnedPUBLIC11/12; retain8+2. Expected:10differentunseenfamilies,fullhashverified,existingfilesunchanged.
- [x] Step 2: Readpublicsources,writeall10fieldgoldunit/exclusionpositions andfreezehashbeforeanymodelrun;markagent-authored/human_reviewedfalse. Expected:noAPI/modeloutputseen;unsuitablefieldsandambiguityexplicit. 207units/29exclusions/12ambiguities; gold5fcdc3a15fdbd346e0e351313639c1ebe2cac02cc36f33abf749d2ff22caa283.
- [x] Step 3: WriteREDtests:exposureoverride/path/hash/duplicatefamily;one-to-onealiases/duplicateoutput/repeatedoccurrence/wrongfield/exclusion/null/absence/unmatched/malformedprofile. Expected:newAPIsmissing. 21 tests RED→GREEN.
- [x] Step 4: Implementstrictsource/goldchecksandtypedscorer. Runfocusedthenalltests/runtime_tests. Expected:noambiguouscredit/noreleaseclaim,norawoutput. Commit/task-done. f83ea0b + bc3ae4e; final1095tests/5skip(41.105s),runtime9pass(38.883s),22focusedpass; actual10source/goldvalid;task-done9af3f2a..bc3ae4e.

Task1 focused command (cwd ai_service): `rtk proxy ../.venv/Scripts/python.exe -m unittest discover -s tests -p test_independent_profile_evaluation.py -v`. Expected RED missing module then GREEN. Whole gate: plan workspace verify.ps1 executes both `-m unittest discover -s tests -v` and `-m unittest discover -s runtime_tests -v`, fails if either fails, prints tails only. Assertions: repeated positive+negative→unassessed1/matched0; samegold twice→matched1/duplicates1; allnull/failed→gold denominator unchanged; wrongfield→known_wrong1; unknownalias→unassessed1; unregisteredemptyarray→unassessed1; malformed source identity→invalid/evidence_invalid1. Corpus tests mutate path/hash/family including cal.com↔cal.diy and unsafe metadata; gold tests duplicateunit/span/boolindex/overlap/falsehumanreview flag.

Self-review: all source, gold, output and failure invariants belong Task1; process/privacy/resume belong Task2; actual complete30 and independent review/CI belong Task3. No production tuning under this branch. Release criteria remain unproved.

Task1 correction: wrong-field known_wrong requires an explicit wrong_role exclusion; merely matching another field's gold is unassessed. A new regression failed1/22 before this fix and all22passed after it. This prevents source-role overlap from creating false error counts. Final whole gate is rerun for this correction.

### Task 2: 実통합 요청 실행기와 재개 가능한 안전 결과

**Files:** Extend independent_profile_evaluation.py; add independent_evaluation_worker.py,test_independent_evaluation_worker.py,tests/test_independent_evaluation_runner.py; local runnerdriver.
**Interfaces:** Worker receivesdocument/docId/twokeys/goldthroughstdin,runsactualexecute_integrated_analysis,returnsboundedtypedscoreonly. Parentexecutiondeadline1800/max30runs;exactcheckpointIDs/config/source/gold/evaluatorhashes,mkdir/newfileonly,neverresumealtered/successfullycompletedrun.

Task2 concrete file/API map (freeze117files unchanged):
- `independent_evaluation_protocol.py`: `validate_score(document: str, gold: dict, score: dict)->dict`. Validate exact Task1 keys, integers excluding bool, approved enums/hash/positions, each field's counts and per-item category sums, IDs against gold, gold/missing identity, no false human/release claim, max128positions/item. Validate only typed contents and copy them; no text keys. For valid score, null fields may retain gold missing; failure/invalid must have no items/produced/matched/questions/states and allgoldmissing. It must not infer semantic correctness from syntax validation.
- `independent_evaluation_worker.py`: `execute_request(packet: dict)->dict` + `main()->int`. Input5keys as spec; validate_gold and IDs before actual execute_integrated_analysis; reject empty/equal/oversized keys and key appearing in document/id. Input JSON1MB/output1.5MB. Suppress SDK stdout during invocation, never print exception/string contents. Boundary errors emit only {'error':'INVALID_EVALUATION_INPUT'} and nonzeroexit; valid analysis errors become failedscore with safe_code.
- `independent_evaluation_runner.py`: `async run_scored_process(document: str, document_id: str, gold: dict, solar_key: str, nvidia_key: str, *, timeout_seconds=1800, command=None)->dict`. Same disposable process pattern as analysis_process, sanitized env, stdin-onlysecrets, stderrDEVNULL, outputsizebound, deadline covers creation/write/read/wait, finallykill/wait on timeout/cancel. Timeout→failedscoreANALYSIS_DEADLINE, invalidchild/exit→failedscoreANALYSIS_FAILURE. Testcommand injection confined to explicit function arg, CLI has no command flag.
- runner `prepare_evaluation(corpus_file: Path, gold_file: Path, freeze_file: Path)->dict`: paths read bounded, corpus top exactversion/cases/excluded_reserved_ids/authoring_stage; 10cases/allgoldaligned; prior fixedspecmanifest; sources from gold_file.parent; freeze settings exactspec; hashes for every originally frozenfile plus evaluator modules; goldsummary expectedhash. Returns in-memory sources/gold and content-free experiment metadata. No network or keys.
- runner `async evaluate(prepared: dict, output: Path, solar_key: str, nvidia_key: str)->dict`: exact experiment.json config/hash match, newexclusive manifest/checkpoints,3runs/case, validate existingterminal against original input/score before skip. started-only refuses duplicate calls. no overwrites. print only case/run/status/aggregatecounts. Terminal rows exact speckeys. Total completed/failed/invalid/fieldcounts/questions/latencies and release_gate_passed=false; partial never passes. Error codes only, no exceptionstring.
- CLI main flags as spec, allpathsrequired; --live required before readingsecrets/callingAPI. Load exactly one nonblank UPSTAGE_API_KEY and NVIDIA_API_KEY from specifiedenvfile, surrounding matchingquotes allowed, reject duplicates; no os.environ fallback. Fixed configured1800sec,3runs,10cases. Generic failure prints {'error':fixed_code}; KeyboardInterrupt leaves startedrecord and child cleanup.
- Task2 boundary refinement: put `prepare_evaluation` and bounded metadata/key readers in `independent_evaluation_inputs.py`, re-export prepare_evaluation from runner. Metadata hashes use sorted compact JSON UTF8 so Git CRLF cannot change experiment identity; original source/goldfile hashes remain exact bytes. Prepared input carries absolute metadata paths, source/gold memory and typed experiment metadata. Re-run preflight before every new launch and require metadata identity with initial snapshot; existing results are all validated before any new call. evaluator hash covers six new modules (corpus/profile/protocol/worker/inputs/runner), frozen117 coverage must equal remaining current productionpy/requirements paths.
- New tests: `test_independent_evaluation_worker.py`, `test_independent_evaluation_runner.py`, `runtime_tests/test_independent_evaluation_runtime.py`. Keep synthetic fixture/protocol doubles in tests; use actual SDK+loopback provider for full worker runtime (existing integrated_service_fixture approach, only loopbacknetworkallowed).
- RED assertions: injected raw/error/extra keys rejected; mismatch source/id/gold denied before provider callback; malformed child/oversizedoutput/timeout yield allgoldmissing; canceled child terminates; required10docs and tampered source/gold/code fail before anylaunch; same experiment resume produces0newcalls for alreadycompletedrows; started-only/config mismatch/corruptterminal raises fixederror before furthercalls; emptyoutput produces30terminalrows via synthetic providers; outputfiles contain no synthetic secret/source text. Every meaningful failure keeps its case/run and denominator.

- [x] Step 1: Finalizeexactstdin/output/checkpointformatsinthespecandbriefbeforeREDtests. Testactualchildsafeerrors/timeout/duplicatecheckpoint/configmismatch/rawexclusion plusin-memoryfakeproviderstatus. Expected:newrunnerAPIsmissing. Worker7/process5/input4/checkpoint5 RED→GREEN; combined21passed5.579s.
- [x] Step 2: ImplementdefaultCLIwith--live,--env-file,--corpus,--gold,--freeze,--output; preflightall10thenperrunprocess/checkpoint. No externalcallunlessliveandallhashespass. No modeloutputinstdout/files. Actualpreflight10cases/207goldunits passed, original117filesunchanged; evaluator8d6ab064551419943e18732dd5ba96763f8cbb1faeb029ec4470f6dd78f70f49.
- [x] Step 3: ActualSDK+loopbacktestthroughnewworker,failedrowsretained,resumecompletedrowswithoutAPI. Fulltests/runtime_tests/commit/task-done. da49dfb; final1117tests/5skip(48.072s),runtime11pass(40.310s); Task2complete ebcb9e9..da49dfb. Push/exactCI36720782159 bothjobs success.

### Task 3: 실제30회 기준선·전체 검토·인계

> 사용자 목표·비용 조건 변경으로 실제 호출 중단. 완료1/30, 중단1회 결과·고정파일 보존. 현재 모델 조합은 Solar를 포함하며 유료 승인이 없다. NVIDIA 계정의 추가 요금 없는 엔드포인트도 확인 전이다. Task3를 완료로 표시하지 않는다. 재개 시 사용자 조건과 started-only 복구를 먼저 검토하고 기존 완료 요청은 재호출하지 않는다. 원래 호출 상한30×64=1920(재시도 포함), 요청별1800초·NVIDIA503추가1회, 전체 최대15시간. 지금부터 승인된 외부 모델 호출 예산은0이다. 로컬 핵심 흐름 mock·계약 테스트는 별도 feature로 진행한다.

**Files:** specfolder/validation.md,work/harness/independent-profile-evaluation/{STATE.md,review.md,REMOTE.md};ignored typedresultfiles.

- [ ] Step 1: Freezeallsource/gold/config/evaluatorhashes,run3percasewithactualSolar/NVIDIAkeys;storeandinspectonlytypedmetadata. Observeconfirmedlivehandle,norestartontimeout. Expected:30terminalrowsincludingfailures,partialisnotcomplete.
- [ ] Step 2: Aggregateexactmatchcoverageandknownwrong/unassessedbyfield+eachrun;reportsource/annotation/generalization/humanreviewlimits. Do nottuneagainstthesameheldoutduringthisrun.
- [ ] Step 3: Fullcodeverification/freshwholebranchreviewonce,fixCritical/ImportantRED→GREENifany,push/exactCI. Expected:reproduciblebaselineandconcretenextqualityfailure,fullgoalstillincompleteunlessallindependentrequirementsproved.
