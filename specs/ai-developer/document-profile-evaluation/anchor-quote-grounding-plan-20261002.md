# Anchor 큰따옴표 차이 — 제한된 원문 위치 연결 수정

사용자가 승인한 작은 버그 수정. 기반 e5ec802. 큰 Goal paused. 브랜치 feature/anchor-quote-grounding.

## 재현 근거

동결 trace 호출3의 operation mentions[18]에서 quote는 `PDF · Markdown · 텍스트 입력`, anchor는 곡선 큰따옴표 U+201C/U+201D다. 원문은 ASCII U+0022이며 현재 결과는 ambiguous_anchor다. quote는 원문 Unicode [1890,1913)에 존재한다. 원문/trace/gold는 기존 review_preservation fixture와 해시를 재사용한다.

## 구현 명세

- 정확한 연결을 먼저 시도한다. 정확 anchor가 여러 번 있거나 후보가 anchor에 없거나 여러 번 있으면 기존 실패를 유지한다.
- operation 추출 호출에서만 내부 선택 인자로 보조 연결을 켠다. 다른 기존 grounded extraction 소비자의 기본 동작은 바꾸지 않는다.
- 정확 anchor가 없을 때만 비교 문자열의 U+201C/U+201D를 ASCII 큰따옴표로 1:1 치환한다. single quote, backtick, dash, whitespace, case, Unicode 조합 정규화·유사도 검색은 하지 않는다.
- 정규화 anchor가 전체 문서에 단 한 번 있어야 한다. 후보는 제공 anchor에 정확히 한 번 있어야 하며 원본 문서 slice와 정확히 일치해야 한다. 후보 값 자체를 비슷한 값으로 고치지 않는다.
- 모든 치환이 Unicode 1문자→1문자이므로 위치는 원본 인덱스와 같다. slice equality를 검사한다. 원문/추출 입력 객체는 수정하지 않는다.
- 기존 interval conflict·duplicate span 검사를 유지한다. 성공 reason만 내부적으로 anchor_quote_variant로 구분한다. 실패 이유와 frozen 후보 계약, v3 응답 계약은 유지한다.

## 실행 계획

1. 기존 실패 및 유일 위치/중복/잘못된 문맥/CRLF·한글·이모지 대조 테스트를 먼저 작성·실행한다.
2. ground helper와 operation caller에 최소 변경한다. 저장 operation 응답1개만 재생하고 후보 집합 변화까지만 관측한다.
3. v3 회귀는 동결된 operation grounding 이후의 고정 후보 집합을 사용하도록 테스트 fixture 경계를 명시한다. 새 후보를 이전 분류 응답에 추가하지 않는다. 모델·의미 정책·골드는 불변이다.
4. 관련 회귀와 응용 소켓 차단 검증, 최종 리뷰, 결과 기록 후 로컬 커밋하고 종료한다. 이번 외부 네트워크 전송 금지에 따라 push는 하지 않는다.

실제 API 호출0·재시도0. 로컬 조사/구현/검증 목표 상한2시간, 개별 테스트 실행5분. 의존성 설치·운영 적용·큰 Goal 재개 없음.

## 완료 기준과 한계

- 위치 복구 수/원문 값·인덱스만 성과로 집계한다. 새 후보의 분류·검토·Profile 의미 보존은 미측정이다.
- 기존40개 의미의 누락0을 주장하지 않는다. 새 후보가 모델 입력/ID 구성을 바꾸므로 이전 전체 파이프라인 결과를 새 결과로 재사용하지 않는다.
- 위치 미확정 후보의 frozen rejection은 index/reason뿐이다. v3 disposition은 유효 source span을 가진 modelDecisions 후보만 받으므로 현재 계약으로 미확정 위치를 후보별 확인 대상으로 전달할 수 없다. 계약 확장은 범위 밖이다.

## 완료 기록

- [x] 저장 응답의 ambiguous_anchor와 원인 재현, 새 회귀 RED 확인.
- [x] operation 경로에서만 exact-first 보조 연결 구현, 동일 응답42→57개 위치 연결. 기존42개 불변.
- [x] 새12회귀·기존v3 18회귀 통과. 독립 리뷰52건 통과/추가 수정 사항 없음.
- [x] 최종 오프라인 전체1404통과·7skip·실패0, TCP29제외. 원문/trace/gold 해시 보존.
- [x] 새 후보의 후속 판단은 미측정으로 남기고, 기존 v3 회귀는 동결된 이전 후보 경계에서만 재생.
- [x] 결과와 계약 한계를 anchor-quote-grounding-report-20261002.md에 기록. 큰Goal paused, 모델/외부전송/서비스적용0, push 없이 종료.
