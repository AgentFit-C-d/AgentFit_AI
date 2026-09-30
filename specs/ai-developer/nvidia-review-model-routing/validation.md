# NVIDIA 검토 모델 선택 검증

## 구현과 현재 범위

명시적 선택을 CLI→준비/freeze→평가→부모→자식→기존 분석기로 전달한다. 공개 HTTP API와 기본 GLM 검토, 프롬프트·채점·64호출/1800초·재시도0은 유지한다. 구현 검증은 합성 자료와 loopback 서버를 사용하며 외부 모델 호출0이다.

## 확인한 결과

- Task1: 전달·거절·기본 packet·모델 trace 검증 RED→GREEN. 새+기존 메타데이터14/14, 기존 process11/11 통과.
- Task2: 옵션 없는 기존 구현에서 평가4tests10errors/runtime4tests6errors RED. 구현 후 새+기존 평가20/20(11.278초), 실제 SDK/자식/loopback4/4(16.835초) 통과.
- 같은 합성 입력의 기본5호출은 DeepSeek3→GLM2, 선택 경로는 DeepSeek5로 기록되고 점수/단계/호출 수는 같다. 이 fixture는 기능 큐레이션 호출이 없다.
- 선택된 검토의503·429는1회 실패 후 멈춘다. 응답 모델 불일치 거절, timeout/cancel 후 자식·socket 정리, 재개/manifest/성공·실패 행의 모델 위조 거절을 확인했다.
- 오프라인 실제CLI 사전 점검: 공개10문서/예정30요청/임시gold207개/코드126파일, 선택 reviewer DeepSeek. 키 읽기·모델 호출 없음.
- 새 freeze `f5e1f64b667a075046680182dba86456417af1894304916813377e61ccd3eba5`, evaluator `c8a023265e50ecc1715d9acbc5a070e368ee55c03f368e29b28cc2a60a00d4c5`.
- 기존 세 결과 폴더의JSON·gold·이전 두freeze 총13파일의 등록 전후 해시가 같다.

전체 회귀: 단위1174건 중1169통과/플랫폼skip5(59.825초), runtime31/31(111.089초), 계약36/36(5.170초), core8/8(27.763초). 총1244통과/5skip이며 모든 suite 종료코드0이다. 코드 커밋은 `a28254a370d7c93df447200b994c295aa01d1415`다. 독립 최종 리뷰 Critical0/Important0/Minor0, 메인이 리뷰 패키지 인코딩 개선 권고를minor deferred로기록했다. push/CI는 후속확인한다.

## 원격 검증

`feature/nvidia-review-model-routing`의 `9b853390a7401df128d85735818a4c27ed7fb010` push 완료. [Linux CI36768519813](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36768519813)는2026-09-30T19:53:48Z에모든4job이success로종료됐다. 단위·실제Linux메모리·통합SDK·계약mock·핵심흐름을포함한다. 이후실제평가는별도[실행계획](live-plan.md)을따르며코드/자료freeze를유지한다.

## 별도 실제 평가 완료

고정된 소스로 실제30회 평가가 종료 코드0으로 완료됐다. 계약상 유효한 초안27회·입력 거절3회·잘못된 응답 계약0회, 사용 가능한 진단의 DeepSeek309호출이며 종료 후 관련 프로세스0개다. 기존13개 증거 파일은 불변이다. [최종 보고](live-result.md)와 [구조화 집계](final-summary.json)를 남겼다. 실제 실행과 구현의 합성 검증은 별도 증거이며, 이번 실행에서도 사람 검토와 실사용 gate는 통과하지 않았다.

## 남은 해석 제한

로컬 검증은 선택 모델의 정확한 전달과 오류 처리 증거다. DeepSeek의 실제 문서 검토 품질 향상이나 제공자 가용성을 입증하지 않는다. gold는 사람이 검토하지 않은 임시 기준이며 `human_reviewed=false`, `release_gate_passed=false`를 유지한다. 실제Spring·DB·운영 환경은 미검증이다. 이전 진단의 첫GLM HTTP5xx 실패1건만으로 모델 일반 성능을 단정하지 않는다.
