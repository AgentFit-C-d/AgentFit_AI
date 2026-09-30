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

## H02v2 중간 상태 / CI

- false조건은 첫20후보에서 stop/307completion tokens로 응답했으나 REJECTION_REASONS_ROW_SHAPE로 거부됐다.1호출/61.819초, 의미 판단·6부분정답은 미평가. true조건은 같은 실행에서 독립적으로 진행 중이다. 중간 상태를 최종 결과로 해석하지 않는다.
- response_format 제거는 schema에만 있던 상세 행 구조 설명도 제거한다. schema를 프롬프트에 보존하는 후속 보완 후보가 있지만, 이 실패의 실제 잘못된 행 키는 보관하지 않았으므로 미확인이다. 현재 실행 종료 전 제품 코드는 바꾸지 않는다.
- feature/deepseek-review-thinking의8a50ca09546d2972f1831ec1fee2505914c18f2c push 확인. [정확한 CI36684252850](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36684252850) completed/success, 두job 모두통과. 실제 품질·최종 독립리뷰·전체 실사용 완료의 근거는 아니다.

## H02v2 최종 결과

- session95687/PID36508 terminal/exit1.2호출/526.863초. 코드3140938로 고정된 실행이었으며 종료 후10항목 감사 통과. 현재 이 프로세스는 재시작하지 않는다.

| 조건 | 실제 호출 | 최종 결과 | 의미 평가 |
|---|---:|---|---|
| thinking=false, schema-off | 1 | 후보1묶음 REJECTION_REASONS_ROW_SHAPE, stop/307tokens,61.817초 | 16개 판단·6개 부분정답 미평가 |
| thinking=true, schema-off | 1 | 후보1묶음 length/8192tokens, INCOMPLETE_RESPONSE,465.029초 | 16개 판단·6개 부분정답 미평가 |

- 비교 실패를0% 정확도로 바꾸지 않는다. thinking의 의미 품질 우열·기본 모델 채택 근거가 없다. 최초3+진단2+v2합성4+H02v2 2=전체 실제11호출로 종료했다.

## 후속 코드 보완 / 이번 기능의 한계

- 자연어에는 없고 schema에만 있던 정확한 행 키·추가 속성 금지·배열 규칙을 제거하던 경로를 회귀 테스트로 재현(RED). 선택형 schema-off에서는 그 schema 전체를 system prompt에 넣고 guided decoding만 제거하도록 수정(GREEN10/10,0.013초). 원문/user 메시지 불변·두 조건 대칭·schema 완전 일치·서버 검증 유지 확인.
- 실제 API가 terminal이며 frozen 코드 감사가 끝난 뒤에만 이 수정을 했다. 이 최종 프롬프트 보완의 실제 모델 성공률은 아직 미검증이다. 추가 API는 이번 기능에서 실행하지 않음.
- 생각을 많이 하다 출력 상한에 닿는 문제는 별도다. 정확한 추론 설정 또는 토큰/시간 설계 변경을 사전 고정한 후속 실험이 필요하다. 이번 결과만으로 semantic accuracy나 실사용 완료도를 높이지 않는다.
