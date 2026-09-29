# 분리 검토 호출 진단 계획

> executing-plans와 TDD로 직접 진행. 명세: [spec.md](spec.md)

**Goal:** 검토 실패의 호출 위치·종료 사유·토큰 수를 확보한다.
**Architecture:** 기존 `_trace`에서 고정 메타데이터만 복사하고 평가 행에 실패 시에도 남긴다.
**Tech Stack:** Python/unittest, 기존 Solar transport.

## 제약 및 검토 초점

원문·응답·키·예외문 미출력. 불완전 응답과 잘못된 계약을 구분하되 모델 요청은 그대로다. unknown finish_reason과 malformed usage, 실패 이전 호출 메타데이터, 기본 경로 동일성, CLI 조합 오류를 검증한다.

- [x] 1. 실패 응답의 stage/batch/finish_reason/tokens와 민감 데이터 미포함, 수집 전후 요청 동일성 테스트 RED. CLI 실패 행 보존·조합 검증 RED.
- [x] 2. solar._send_payload trace에 안전 finish_reason 추가. 분리 검토에 선택형 review_calls 수집기 추가. 분석기/평가 CLI를 연결하고 관련 테스트 GREEN.
- [x] 3. 전체 테스트와 diff 검사·독립 리뷰·commit/push·CI. H02 진단 평가 한 번 실행 후 실패 위치와 다음 결정을 validation.md에 기록한다. 묶음 2의 length/8192 종료를 확인했다.

## 상태

시작 커밋 3294465. 앞선 실험은 코드 검증 완료·실제 검토 미완료. 실행 세션 47832는 종료 코드 1로 끝났으며 현재 이어서 기다릴 프로세스는 없다. 사용자 소유 work/harness/service-readiness는 보존한다.
