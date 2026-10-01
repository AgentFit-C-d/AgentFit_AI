# B 인용문·단위 선택 한 쌍 실험

## 최종 결과 — 완료 후 중단

- 실제 한 쌍18회 완료(Q9+U9), 응답18/오류0/재시도0. 각68개 후보 보존.
- Q→U: 인용 결함21→2, 모델 오확정3→3, gate 통과 오확정2→3,
  정상 누락2/6→0/6, 전체 보류40/68→32/68, 주 평가 보류4/10→1/10.
- 태그 정리·프로젝트명 복구. Clean UI가 정확한 근거를 얻어 잘못 supported로 통과.
  Firefox·Chrome 오확정 잔존. 주 평가10개 raw field/status는 양쪽 모두 같다.
- U 결함: C024 ID hash 복사 오류1, C055 제목-only 구조적 불충분1. 전체68개에 그대로 포함.
  C055는 실제 양쪽 모두 other/confirmed로 보류되므로 추가 보류 차이 원인으로 세지 않음.
- 시간Q152.331초/U457.014초. 단일 문서/한 쌍 결과로 일반화하지 않는다.
- 고정140파일 변경0, 실제 user message9쌍 동일, 과거 원본22파일 변경0.
- 결과 specs/ai-developer/b-evidence-selection-comparison/results.md·results.json.
- 큰 goal paused 재확인. 서비스/관계/Spring/배포/추가 호출0. 최종 기록 commit/push 후 종료.

## 실행 기록 (보존)

- 시작2026-10-01 12:39:31 UTC. 로컬 작업 상한14:39:31 UTC. 실제 한 쌍은 최대3600초.
- 사용자 승인: B의 근거 방식만 비교, 무료 NVIDIA 최대18회/재시도0/결과 보고 후 종료.
- 브랜치 feature/b-evidence-selection-comparison, 기준487b83a. 기존 dirty 파일 그대로 보존.
- 목표 paused 확인. 관계 검증기·서비스·Spring·배포·Luna·추가 반복 제외.
- 무료 근거: 사용자 확인 기록 유효(만료2026-10-01 17:32:45 UTC), DeepSeek/endpoint 일치.
  독립 계정 과금 조회가 아니며 매 호출 전 scope/만료·동결 hash 재검사한다.
- SDD 명세/계획 작성 완료. 같은 user message, 분류 지시·모델·후보·정답 고정.
- Q는 기존 B quote/occurrence, U는 unit IDs. 단위 목록을 양쪽에 추가하여 입력 문맥을 동일하게 한다.
- 남은 작업: RED/GREEN → 전체 로컬 회귀/검토 → freeze → 무료 확인 후 한 쌍 → 보고/push/종료.

## 로컬 구현

- experiment.py/evaluate.py 및 신규 회귀11개 구현. 새 의존성·기존 서비스/비교기 변경 없음.
- RED: 빈 구현에서 동일 문맥/원자료 재현/오확정 보존/실패 중단 검사가 실패함을 확인.
- GREEN: 신규11개 통과(0.774초), 기존 B 저장 결과68개 그대로 및 인용 결함22건 재현.
- 고정 응답 대조: 같은 wrong field/status를 둔 채 근거만 복구하면 태그 정리가 supported가 되고
  Clean UI도 잘못 supported가 된다. 이 위험을 숨기지 않는 회귀를 추가했다. 실제 모델 결과가 아니다.
- durable 18회 gate와 원응답 저장, 무료 확인·hash 재검사, 최초 실패 중단·재시도0을 재사용.
- 코드·입력·정답·무료 기록 동결과 live marker로 중복 실행을 차단한다.
- 전체 로컬 회귀1340개 실행,1333 통과/7 skip/실패0,97.816초.
  로그 E:/AgentFit/output/b-evidence-selection-local-tests.log.
- 최종 독립 검토 진행 중. 아직 모델 API 호출0. freeze/live 전에 검토 결과를 반영한다.

## 최종 검토와 수정

- Important1: U schema 재구성에서 status가 근거 앞으로 이동한 추가 변수 발견.
  신규 순서 회귀의 RED 확인 → 근거 키를 원위치에서 대체하여 Q/U 생성 순서 동일하게 수정.
- Minor1 보고 한계: C055 제목 후보는 E1 nonheading 조건상 구조적 보류가 필연적이다.
  E1/gold 변경 없이 전체68개 집계에 포함하고 결과에서 모델 선택 오류와 구분한다.
- 판단 제외에 대한 결정: 실제 계정 청구 화면의 독립 확인·관계 검증·서비스·goal·다중 반복은
  사용자 범위 밖으로 유지한다. 표현별 근거 상한 차이와 한 쌍의 통계적 한계를 결과에 명시한다.
- 수정 pass는 위 순서 문제 한 건에 한정. 신규12개와 전체 회귀 재검증 후에만 freeze/live.

## 실제 한 쌍 시작 준비

- 순서 회귀 RED→GREEN, 신규12개 통과. 최종 전체1341개 실행/1334통과/7skip/실패0,90.664초.
- 최종 코드 ef0ac09. Q/U 실제 user message9쌍 완전 일치, 최대 요청 약52.5KB.
- 입력 원본·gold·기존 B·registry·서비스 diff0. 기존 다른 작업의 dirty 보존.
- 이 코드로 freeze 후 live를 한 번만 시작한다. 이후 코드/입력/gold/모델을 수정하지 않는다.
- 출력 예정: E:/AgentFit/output/b-evidence-selection-v1. Q=gate A, U=gate B, 최대18회/재시도0.

## 실행 중

- freeze 완료, live 명령1회 시작. tool exec session13490. 같은 output으로 재실행 금지.
- 첫 확인: Q2배치/16후보 완료, Q3배치 진행. 코드·입력 동결 유지, 오류/재시도 없음.
- 이어받을 때 calls/*-started/finished/response.json 및 summary.json부터 읽어 중복 호출을 피한다.
