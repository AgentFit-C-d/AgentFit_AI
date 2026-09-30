# NVIDIA 단독 비교 평가 명세

## 목적과 현재 근거

단독 분석 서비스는 f0d57dd에서 로컬/CI 검증을 마쳤다. 기존 공개10문서×3회 평가 도구는 Solar 키와 과거 코드 해시에 고정돼 있어 그대로 사용할 수 없다. 실사용 목표에 필요한 실제 품질 검증을 준비하되, 중단된 혼합 baseline과 원문/임시 정답/채점 기준을 보존한다. 사용자 목표의 자율 설계·계획·직접 구현 승인을 적용한다.

이번 변경은 평가 실행 경계의 구조 변경이다. 선택지는 기존 baseline 설정 덮어쓰기, 전체 평가 복제, 별도 variant에서 기존 채점·체크포인트·서비스 자식 재사용이다. 마지막 안을 선택해 결과 혼합과 채점 기준 변경을 막는다. 기존 평가6모듈/서비스 동작/공개 API는 변경하지 않는다.

## 고정 자료와 설정

- variant `nvidia-only-v1`, 모드 integrated-nvidia, confirmation-v2. 추출/분류/기능 DeepSeek4.1Flash, 검토 GLM5.3. 현재 엔진과 같은 모델, 최대64호출/요청1800초/자동재시도0.
- 기존 corpus.json/로컬 gold.json과 이전 보류 문서 목록 검증을 재사용한다. PUBLIC-01,02,03,06,07,08,09,10,11,12 각3회, 총30회. 원문·정답 바이트 해시를 그대로 확인한다.
- 신규 freeze.json은 모든 agentfit_ai/*.py와 requirements*.txt의 LF 정규화 해시, corpus/gold/prior 해시와 정확한 설정을 보관한다. 모듈 추가/삭제/수정도 실패한다. evaluator 해시는 기존 채점3모듈과 새 평가2모듈, 재사용 체크포인트 모듈을 포함한다. 구현 완료 후 로컬 도구로 생성하며 소급 갱신하지 않는다.
- 원래 baseline이1/30에 중단돼 완전한 비교가 불가능하다고 명시한다. new_holdout=false, human_reviewed=false, release_gate_passed=false. 에이전트 임시 정답으로 출시 승인이나 의미 정확도 확정을 하지 않는다.

## 실행과 비용 경계

1. 기본 CLI는 키를 읽지 않고 모델을 호출하지 않는 preflight다. `--live`와 env/output/무료확인 파일을 명시해야 실제 평가로 진입한다. 이번 작업에서 실제 API0회/유료0원/배포0, 기존 실제 평가 재개 금지.
2. 무료확인 파일은 version=nvidia-free-access-v1, confirmed_no_additional_charge=true, endpoint=https://integrate.api.nvidia.com/v1/chat/completions, models=[deepseek-ai/deepseek-v4.1-flash,z-ai/glm-5.3], expires_at=UTC ISO8601, max_model_calls=64~1920 정수, evidence=비밀이 없는1~200자 확인 자료 식별자다. 정확한 키/형식/미만료를 검증한다. 사람이 계정 자료로 확인한 기록이며 도구가 계정·과금을 조회했다는 뜻은 아니다. 승인된 실제 기록이 없으므로 이번 작업에서는 합성 파일만 테스트한다.
3. `.env`에서 NVIDIA_API_KEY만 읽으며 Solar 키는 요구하거나 사용하지 않는다. 키/원문/모델 원본/무료확인 원문은 로그나 결과에 저장하지 않는다. 정확한 점수·해시·안전한 오류 코드만 기록한다.
4. 전체30회, 매 요청64회를 보수적으로 예약한다. 기존 started 기록을 포함한 누적 예약이 무료확인 max_model_calls를 초과하면 새 요청 없이 중단한다. 실제 사용량/청구액으로 오인하지 않도록 `reserved_model_calls_upper_bound`로 보고한다. 무료확인은 매 새 요청 직전에 다시 읽어 만료/철회를 반영한다.
5. 기존 NVIDIA 서비스 `run_analysis_process(..., nvidia_only=True)`를 실행한다. 부모가 gold로 채점하며 Profile은 메모리에서만 사용하고 결과 파일에는 기존 strict score만 쓴다. 별도 복제 worker나 gold의 모델 전송은 없다. 같은 요청 기한과 cancellation/reap을 적용한다.
6. checkpoint는 기존 strict 형식과 생성 전용 파일 쓰기를 재사용한다. 별도 버전 experiment.json이 기존 baseline 폴더를 거부한다. 모든 기존 row 검증 후 시작하며 완료 row 재실행/started-only 자동 재실행/소스나 코드 변경 뒤 계속 실행을 금지한다.
7. provider 인증/권한/429/503/연결/timeout 등 외부 상태 오류는 해당 실패 row를 저장한 뒤 전체 평가를 중단한다. 재실행해도 해당 중단 row를 확인해 자동 진행하지 않는다. 실제 계정 한도 소진을 의미하는지 추측하지 않으며 유료 fallback/충전/자동재시도는 없다. 구조/의미 오류는 실패로 분모에 유지한다.

## 검증과 예산

- preflight: 10문서/임시 정답, 코드·문서·gold·설정·추가 파일 변경 거부, 기존 baseline 분리. 기본 CLI가 키/실행에 접근하지 않음.
- 비용: 확인 누락/false/만료/다른 endpoint·model/잘못된 정수/누적 예약 초과에서 실행0, 실행 중 만료·provider429/503 뒤 추가 요청0.
- 결과: 합성30회와 재개0회, 변조/미완료 checkpoint 거부, 키/원문 비노출, 실패도 gold 분모 유지.
- 실제 SDK/loopback/NVIDIA 자식으로10필드 채점/구조오류/429/timeout/cancel 종료 검증. 기존 단독 서비스 shim을 사용한다.
- 작업45분 점검, 각 suite180초, 합성 자식30초/기한테스트1초, 실모델0/유료0/자동재시도0. 전체4suite→독립 리뷰1회→feature push→정확한 HEAD CI.

## 자기 검토

품질 평가 준비를 실제 품질 개선으로 표현하지 않는다. 비교 자료/채점기는 유지되지만 모델과 실패 중단 정책은 달라 manifest에 명시한다. 전체 목표의 실제 Spring·계정 무료 범위·사람 정답 검토는 미완료로 유지한다.
