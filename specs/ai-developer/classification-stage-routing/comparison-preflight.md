# 전체15묶음 비교 사전 검사

- 실행기: work/harness/classification-stage-routing/full_comparison.py. 실제전송은 기존600초 subprocess 전송을 사용한다. 새 옵션의 직접 실행이며 부모 stdin으로 키를 전달하는 기존 provider 경계를 유지한다.
- source-validation-freeze.json과comparison-freeze.json을 새로 작성. comparison freeze digest:59ec853ed90940fc3c98ce4fb7ad6ee9a66ca1fa24efd2180956cbcfcab3d136.
- 입력 PUBLIC-01=173,PUBLIC-07=36,SYNTHETIC-01=16. 각12/3/2호출×두모델=34. 재시도0. preflight시 출력폴더 없음.
- 로컬 helper 검사:8PASS0.687초/API0. 원문/후보·모델간 payload 일치,전체34호출계산,실패후중단,무료만료0호출과사유보존,기한0호출,최종묶음잘못된ID거절,출력덮어쓰기거절,고정코드/후보hash불일치0호출.
- 최초7검사 중 무료만료가일반CLASSIFICATION_FAILED로기록된1실패를확인했다. 고정된무료/입력오류코드만보존하도록 수정후전체8PASS. 자유예외문자열/키/원문출력0.
- 무료확인파일은 기존20261001사용자확인,만료/범위/예약34회매전송검사. 예약수는계정잔량이아니다. 유료전환/미확인모델대체0.
- 기존추출의거절개수1/0은 별도 identity로 보존. 새로운분류요청은정확후보만사용하며원문·ID·순서·위치는기존trace와검증했다. 과거frozen의거절배열을복원했다고주장하지않는다.
- 실제품질평가는아직미실행. 코드547c76a의LinuxCI4작업success,독립리뷰완료. helper와새등록을push하고실행직전preflight재확인후시작한다.
