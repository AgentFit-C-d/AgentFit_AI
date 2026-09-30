# 추론 비교 검증

## 구현 검증

- RED: 새 모듈 부재로 unittest import 실패/exit1.
- GREEN: 신규7/7,0.008초. payload Boolean 단독 변경, 입력 불변, 두 조건 격리, API 전 snapshot/gold/key 확인, length·계약·제공자 오류 미평가, observer 오류 즉시 중지, 비밀 배제.
- 전체:1003건 중998통과5제외,20.062초. 실제 LangExtract SDK4/4,0.044초. 검증 환경은 analysis-runtime/.venv,Python3.13.3,LangExtract1.7.0. 선택적 Docling/reportlab 관련 제외는 유지.
- 검증 래퍼 첫 시도는 PowerShell의 Stop 설정이 RTK stderr 알림을 오류로 간주해 중단했다. Continue와 실제 native exit code 판정으로 수정한 위 재실행은 exit0.

## 실제 평가 준비

- 새 .venv는 python-docx가 없어 H02 준비가 중단됐다. 공용 환경 설치/변경 대신 기존 grounding-venv를 사용한다. 런타임별 결과를 섞지 않는다.
- 고정183후보 원본은 operation-candidates-h02-20260930-v1.json이다. sorted JSON SHA256 b3072792ee68f6ec02655bcb152f44606047cd094744d4117430414019c3256e. 이 파일의 merged_refs가 기존 rejection 보고서의 classification_refs와 완전히 같음을 확인했다.
- snapshot 최초 참조 착오를 바로잡은 preflight는 성공:183후보/16판단/6부분정답/14호출상한. manifest·원문·redacted hash 확인, API0.
- 로컬 드라이버: E:/AgentFit/tmp/run-deepseek-thinking-h02-v1.py. frozen driver SHA256 4c3b8a0e6dc382b1cbecff0268de5e1f71e81b6b04faf1ee4e85308ff4a4917a.
- 실제 합성/문서 API는 아직 실행하지 않았다. 성공률·채택 판정은 미확정이다.

## 최초 합성 및 형식 진단 (종료)

- 구현4ab4a5c로 probe session5176 종료/exit1,3호출/98.545초. false는3/3 및1/1 부분 정답, 후보·coverage 모두 유효. true는 첫 후보 호출 stop/58completion tokens/추론177자였으나 INVALID_RESPONSE로 미평가. gate=false, 최초H02 미실행.
- probe 감사10항목 통과: terminal, frozen code/driver/snapshot hash, 두 조건, 호출 상한, 재시도0, 실패 미평가, 완주만 채점.
- 원시 응답을 보관하지 않아 별도 합성 형식 진단2호출을 사전 기록 후 실행. session32239 종료/exit0,78.339초, 실행 중 코드 불변 확인.
- schema-on/true: content 문자열 아님(0자), reasoning177자 JSON/예상 키 일치/3판단 일치, 공유 parser 거부 INVALID_RESPONSE.
- schema-off/true: content177자 JSON/예상 키 및3판단 일치, reasoning725자 비JSON, 공유 parser 수락. 모든 문자열은 메모리에서만 검사하고 Boolean/길이만 저장.
- 이번 NIM 엔드포인트의 schema+thinking 조합에서 JSON이 reasoning 채널로 들어가는 현상을 재현했다. 모델이 의미 판단을 못했다는 근거와 구분한다. 다른 제공자/버전 전체로 일반화하지 않는다.

## 호환성 옵션과 회귀 수정

- structured_output=False는 두 조건에서 모두 response_format을 제거한다. 서버 JSON·후보 ID·확정성·근거 검증은 유지. 추론 채널 텍스트를 최종 JSON으로 재사용하지 않음.
- 일회성 observer 오류를 공유 parser가 PROVIDER_FAILURE로 감싸고 다음 arm을 실행하는 결함을 새 테스트로 재현했다. 실패 latch를 보존해 첫 오류 후 API가 추가 실행되지 않게 수정. RED RuntimeError 미발생→GREEN, schema-free 인자 부재 RED→GREEN.
- 수정 후9/9,0.010초. 전체1005건 중1000통과5제외,20.144초. SDK4/4,0.043초.
- 별도v2 driver preflight 성공. SHA256 7ea2ed863566aca51b195ef8d2a4c9e03f13af6c8ba74d12aa5716e5e8904722. 동일183후보/16판단/6부분정답. 합성 gate를 다시 통과해야 실제 H02가 허용된다. 최초 결과는 덮어쓰지 않음.

## v2 합성 gate

- 구현3140938 고정. session10533 종료/exit0,4호출/320.782초. false/true 모두3/3 판단 및1/1 부분정답, 후보·전체coverage 계약 유효. true는 reasoning692/719자와 별도의 유효한 최종JSON 응답.
- code/driver/snapshot hash·호출상한·실패분모 등을 확인하는10개 감사 항목 모두 통과, gate=true. 처리 시간은 속도 최적화 근거로 사용하지 않는다.
- 이후 H02v2 session95687 시작. 이 항목 작성 시 실제183후보 결과는 아직 대기 중이며 정확도·채택 판정은 미확정이다.
