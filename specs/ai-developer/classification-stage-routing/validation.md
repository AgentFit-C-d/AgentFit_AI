# 검증 기록

2026-10-01. 실제 외부API0, 기본HTTP·Profile·Spring 변경0.

- Task1: batch_size 미지원 RED→4PASS(0.014초), task-done4PASS(0.015초). 기본30/선택15,31·240후보,반복위치,빈후보 설정검증,누락/중복/타묶음ID/제공자실패.
- Task2: 옵션 미지원 RED6tests/26errors→6PASS(0.025초). 혼합/단독 키·모델 경로,default상속,falsey전송,공유호출한도,최종묶음실패·재시도0·안전진단.
- unit:1246실행,1240PASS/6SKIP,67.262초(exit0).
- runtime:35PASS,127.010초(exit0).
- contract:36PASS,6.337초(exit0).
- core flow:8PASS,28.933초(exit0).
- 합계1319PASS/6SKIP. 각suite180초 제한,전체로그는 이 계획의 SDD workspace에 보존. 기존prefix경고·잘못된CLI입력에 대한예상argparse출력은 테스트실패가 아니다.

독립 리뷰·push·exactHEAD CI는 다음 단계. 이 결과는 가짜 외부 전송과 실제 로컬 SDK/HTTP 흐름을 검증한다. 모델 의미 정확도·새문서·사람 수정량·실제Spring·운영 검증을 대체하지 않는다.
