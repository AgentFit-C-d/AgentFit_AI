# 통합 확인형 서비스 검증

## 현재 확인된 범위

- Task1: v2 계약·Profile 재검증, 전체1049통과/5제외·SDK4통과.
- Task2: inline NVIDIA와 요청별 통합 워커, 전체1063통과/5제외(48.902초)·SDK4통과(0.068초), commit e88b39c.
- Task3 대상 HTTP 테스트39통과(4.349초). 정확한 계약 헤더·인증 우선·body/slot 전 거절, non-null unresolved/[] 보존, 질문/근거 손상·완료/v1 혼용 거절, 키/SDK503, 설정 범위 검증.
- 새 실제 SDK/TCP 테스트5통과(45.612초). 합성10필드 전체 파이프라인과 frontend 확인 필요 상태, 31개 기능의 대표 정리·관계 검토를 HTTP까지 통과했다.
- Solar의 끝나지 않는 헤더와 NVIDIA의 heartbeat 응답 각각에서 전체 기한, ASGI 취소, TCP 연결 종료를 확인했다. 실제 응답 시작 Event를 필수로 확인하고 worker 종료·Provider EOF/연결 종료·동시 요청503·다음 요청 슬롯 재사용을 검사했다.

## 실패 원인과 수정

첫 실제 SDK 실행은 Provider 도달 전 실패했다. 단일 합성 워커 진단에서 테스트용 subprocess.Popen 함수 대체가 Windows asyncio의 Popen 상속을 깨뜨린 TypeError임을 확인했다. 테스트 guard를 클래스 상속으로 변경해 생성만 차단했다. 제품 코드는 이 실패 때문에 변경하지 않았다.

## 검증 경계

실제 LangExtract1.7.0·Profile·분류·검토·대표 정리 구현을 사용한다. 원격 모델 응답만 로컬 합성 서버가 제공한다. 테스트 worker는 네트워크를 해당 loopback 주소 하나로 제한하고 중첩 프로세스 생성을 금지한다. 실제 문서·API 키·외부 API·공용 설치를 사용하지 않았다.

이 결과는 서비스 실행 경로의 검증이며 모델 의미 정확도·새 문서 일반화·사람 수정 부담·실제 Spring 확인/저장·버전 경쟁·실패 원본7일 삭제·배포 완료의 증거가 아니다. 기본 모드와 confirmation-v1은 유지한다. 통합 모드는 선택형이며 자동 complete를 반환하지 않는다.

Task3 커밋 전 전체 단위1073개 중1068통과/5제외(47.225초), SDK/runtime9통과(43.886초)를 확인했다. commit70d69fe의 task-done 게이트도 전체1068통과/5제외(47.185초), runtime9통과(44.892초)로 끝났다.

독립 전체 리뷰1회는Critical0/Important0/Minor0이었다. 검토자는관련99/99(24.499초),runtime9/9(47.406초)를직접실행했다. [리뷰와미검증항목](../../../../work/harness/integrated-confirmation-service/review.md)에판정을기록했다. featurepush와정확한SHA의LinuxCI는최종인계시확인한다.
