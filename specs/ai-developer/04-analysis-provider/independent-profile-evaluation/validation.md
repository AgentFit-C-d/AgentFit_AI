# 독립 Profile 평가 검증 기록

## 2026-09-30 — Task1 자료·정답·채점기

- 분석 production117파일 LF 정규화 SHA256은 사전freeze와 동일하다. 모델/프롬프트 변경 없음.
- 기존 예약10개 중2개는 이전노출로 제외. 남은8개+공식 고정commit Outline/Paperless2개로10계열을 구성,원본파일해시·UTF8·크기 검증 통과.
- 10문서/100필드 원문검토,사전골드207단위·29제외·12모호성. 별도의 사람 검토 없음. gold hash `5fcdc3a15fdbd346e0e351313639c1ebe2cac02cc36f33abf749d2ff22caa283`.
- baseline:1073 tests,1068pass/5skip,49.936s.
- 새 회귀:21개 모두 기능 부재로RED후21/21GREEN(0.041s). 원문 위치 유일매칭/반복·중복/미등록/부재/실패 분모/출처·골드변조를 검사한다.
- 전체:1094 tests,1089pass/5skip,47.637s. 실제SDK 로컬통합9/9,46.560s. 외부모델API0.
- 이 기록은 채점기 동작 검증이다. 새 문서에 대한 모델성능 결과는 아직 없고,의미precision/recall·수정부담·독립사람정답·Spring저장·운영완료를 증명하지 않는다.
- 초기커밋f83ea0b를 feature/independent-profile-evaluation에 push했다. 이후 자체검토에서 다른필드등록만으로오답추론하는 위험을 발견해,명시적wrong_role제외만오답으로 세도록 수정했다. 회귀22개중1개RED→22/22GREEN(0.035s). 이 수정의 전체검증과 정확한 원격CI는 후속 기록으로 확인한다.
- 수정코드 `bc3ae4e`: 최종1095 tests/1090pass/5skip(41.105s),실제SDK통합9/9(38.883s),task-done완료. 10source/gold검증 및 기존117파일freeze일치 재확인. 이후 수정은 plan/validation/STATE 문서 기록뿐이다.

## 남은 작업

- Task3 30terminal결과,필드별누락/명시적오류/미채점 분리,독립전체코드리뷰,push/exactCI.

## 2026-09-30 — Task2 실행기 검증 완료

- 코드 `da49dfb278787174bd35fa4fe777e7242ae4324d`, feature/independent-profile-evaluation push 완료.
- worker/typed score 검증7개, 실제 자식 프로세스5개, 자료·키 사전검증4개, checkpoint5개를 RED→GREEN으로 구현했다. --live 없이 파일·키를 읽지 않는 추가 검증을 포함해 신규 단위 테스트22개다.
- 실제 LangExtract1.7.0·로컬 HTTP/SSE·요청 프로세스 테스트2개 RED→GREEN: 정상10필드 채점, 잘못된 모델응답 실패 시 정답10개 분모 유지. 외부 API는 호출하지 않는 합성 테스트다.
- 최종 전체1117개/1112pass/5skip(48.072초), runtime11/11(40.310초). task-done ebcb9e9..da49dfb 완료.
- 정확한 CI [36720782159](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36720782159)는 위 코드 SHA와 일치하며 unit-and-worker-memory, integrated-runtime 모두 success.
- 실제 자료10개/정답207개·고정 production117파일 검증 통과. evaluator SHA256 `8d6ab064551419943e18732dd5ba96763f8cbb1faeb029ec4470f6dd78f70f49`; 원문/정답 해시는 기존 고정과 같다.
- 결과파일은 위치·해시·개수만 보존한다. 완료행 재개는 재호출0, started-only는 명시적 중단, 손상·설정/자료/코드 변경은 다음 호출 전에 차단한다.

## Task3 실제 평가 — 진행 중

> 후속 상태: 사용자 비용 승인 조건 변경으로 중단. 아래 실행 관측은 이력이다. 89953 exit1 및 runner/worker0개를 확인했고 결과 파일은 보존했다. PUBLIC01/run1은 started-only로 중단되어 채점하지 않는다. 1/30완료이며 실제 모델 기준선·최종 전체리뷰는 미완료다. NVIDIA 현재 계정의 추가요금 없음은 미확인, Solar 유료 호출 미승인이므로 외부 평가를 재개하지 않는다. 무료 확인 전 대체 모델을 호출하지 않는다.

- 코드 da49dfb, 위 evaluator 해시, 10×3회 고정 기준선 실행을 시작했다. 원문·정답·모델 설정을 중간에 조정하지 않는다.
- 로컬 결과: `E:/AgentFit/output/independent-profile-v1/runs-baseline-da49dfb`. 실행·노출 후 상태는 이 기록에 추가하고 사전 고정 manifest의 당시 상태를 소급 수정하지 않는다.
- 2026-09-30 13:26 UTC 관측: PUBLIC-01/run0은247.598초 뒤 ANALYSIS_FAILURE. 골드24개 모두 missing으로 보존됐다. 1/30 terminal, run1 진행 중이다. 최종30행과 전체 코드리뷰가 없으므로 평가 완료·성능 개선·실사용 가능을 주장하지 않는다.
- 확인된 관측 한계: candidate_analysis_pipeline.run은 CandidatePipelineError에 단계·일부 계약 detail을 담지만 candidate_service_worker는 provider_code만 safe_code로 변환한다. provider_code가 없는 계약/내부 오류는 ANALYSIS_FAILURE가 되어 단계가 사라진다. 평가 worker/parent의 예기치 않은 실패도 같은 코드이므로 이번 첫 실패의 실제 단계를 이 결과만으로 특정할 수 없다. 코드상 관측 손실을 확인한 것이며 모델 문제를 입증한 것은 아니다. 현재 기준선은 변경 없이 계속하고, 종료 후 안전한 단계 진단 보존이 필요하다.
