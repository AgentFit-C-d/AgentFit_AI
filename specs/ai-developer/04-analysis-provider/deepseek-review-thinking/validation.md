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
