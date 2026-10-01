# 근거 위치·문맥 연결 구현 계획안

2026-10-01 후속 승인: E1·E2만 오프라인 구현·검증.
현재 실행 근거는 [결과 보고](e1-e2-results.md)와
`work/harness/evidence-relation-repair/EXECUTION.md`를 참조한다.
아래는 승인 당시의 계획을 보존한 것이다. 모델 호출·서비스 적용·S1–S3는 계속 보류한다.

> 이후 구현을 승인받으면 superpowers:executing-plans로 직접 순서대로 실행한다.
> 이번 턴은 계획 작성까지다. 아래 체크박스는 실행하지 않았다.

**Goal:** 저장된 후보 위치로 원문을 정확히 연결하고, 인용 복구가 의미 확정으로 오인되지 않게 한다.
**Architecture:** 기존 코드를 바꾸지 않는 로컬 source registry와 레거시 응답 감사 어댑터를 만든다.
먼저 원문 위치·기존 판정을 보존하는 기능만 검증한다. 새 모델 응답 계약은 문서로만 준비한다.
**Tech Stack:** 기존 Python 표준 라이브러리, unittest, 저장 JSON. 새 의존성 없음.
**Spec:** [spec.md](spec.md) A절. **사례:** [regression-cases.md](regression-cases.md) E01–E10.

## Global Constraints

- 서비스 밖 `work/harness/evidence-relation-repair/`에만 이후 실험 구현을 둔다.
- 모델/API 호출0, 재시도0. `.env`/API key/프로바이더 전송 모듈을 사용하지 않는다.
- 원문은 UTF-8 그대로, offset은 Unicode code point `[start,end)`. HTML·공백·줄바꿈 정규화 금지.
- source registry 상한: 원문24000자/1000단위. 모델 선택 계약: support/counter 각각8단위·4000자 이하.
- 기존 field/status/decision은 변경하지 않는다. 근거 복구만으로 confirmed 또는 supported 승격0.
- 이번 생성 파일은 명세·계획뿐이다. 아래 .py 경로는 미래 구현 대상으로 아직 존재하지 않는다.

## 파일과 인터페이스

| 미래 파일 | 책임 |
| --- | --- |
| work/harness/evidence-relation-repair/source_registry.py | 원문·후보 위치 검증, 단위 생성, 선택 참조 해석 |
| work/harness/evidence-relation-repair/legacy_audit.py | 원래 인용의 결함 분류와 원래 판정 보존 |
| ai_service/tests/test_candidate_source_registry.py | 위치·해시·반복·문맥 상한의 오프라인 검사 |
| ai_service/tests/test_legacy_evidence_audit.py | 실제 저장 응답/합성 응답의 비승격 회귀 |

## Task E1: 후보에서 원문 위치와 줄 단위 만들기

**Consumes:** 불변 `document:str`, `frozen:dict`(candidate id/start/end 및 rejected).
**Produces:** `build_registry(document: str, frozen: dict) -> dict` 및
`resolve_units(registry: dict, candidate_id: str, support_ids: list[str], counter_ids: list[str]) -> dict`.

registry에는 sourceDigest, units, candidates, complete, issues가 있다.
각 candidate는 mentionSpan/value/localUnitIds/headingUnitIds를 가진다.
unitId는 동일 sourceDigest와 `[start,end)`에서 결정적으로 생성한다. 이름이나 정답 ID를 사용하지 않는다.
resolve 결과는 source 위치/문자열/후보 포함 여부/문맥 완전성만 담는다. 의미 판정은 없다.

- [ ] E01–E08/E10의 테스트를 먼저 작성한다. 핵심 불변식:
  `value == document[start:end]`, `unit.text == document[unit.start:unit.end]`.
  두 번 나온 같은 이름은 서로 다른 occurrence를 유지한다.
- [ ] 테스트 실행: `rtk proxy <venv-python> -m unittest discover -s tests -p test_candidate_source_registry.py -v`.
  cwd=ai_service. 예상 RED: 새 함수가 없거나 요구 결과와 불일치.
- [ ] 함수를 구현한다. `splitlines(keepends=True)`로 원문 offset을 누적한다.
  Markdown 제목 줄은 컨텍스트 메타데이터로 보존하고, 그것만으로 후보 위치를 대신하지 않는다.
  여러 줄 후보는 겹치는 줄들을 모두 연결한다. 표는 표 헤더/이웃 행도 독립된 줄로 제공해 임의로 합치지 않는다.
- [ ] 잘못된 hash/범위/중복 후보는 안전한 계약 오류. 크기 초과는 incomplete와 원래 후보 목록을 반환한다.
  문자열 자르기·가까운 일치·첫 등장 치환으로 입력을 몰래 고치지 않는다.
- [ ] 같은 테스트를 GREEN으로 검증하고 해당 소스·테스트·명세만 커밋한다.

## Task E2: 저장 응답을 상태 변경 없이 감사하기

**Consumes:** E1 registry, 원형 보존 raw quote/occurrence 및 기존 정규화된 candidate record.
**Produces:** `audit_legacy_record(document: str, registry: dict, raw_row: dict, saved_record: dict) -> dict`.

출력: originalRecord의 사본, mentionLocated, contextAvailable,
legacyCitationStatus(`valid_covering / exact_elsewhere / quote_not_found / incomplete_context`),
supportSpans, sourceDigest, issues. 어떤 필드에도 수정된 decision을 쓰지 않는다.
여러 결함이 공존하면 issues를 모두 보존하며, 요약 주 사유는 quote_not_found→exact_elsewhere 순으로 기록한다.

- [ ] 저장 사례 B C004–C007, A C022, A/B C035·C066으로 먼저 실패 테스트를 만든다.
  C004와 C005 모두 mentionLocated=true가 되더라도 originalRecord.verdict가 그대로 보류여야 한다.
- [ ] 저장 원자료는 audit.json의 해시로 읽는다. fixture 배포가 필요하면 승인된 공개 자료의
  최소 문맥/응답만 test fixture로 복사하고 원본 해시·offset 변환표를 남긴다. 절대 경로 존재를 CI 전제조건으로 두지 않는다.
- [ ] `rtk proxy <venv-python> -m unittest discover -s tests -p test_legacy_evidence_audit.py -v`로 RED를 확인한다.
- [ ] exact quote는 그 원문 span에만 매핑한다. 실패 인용은 raw 그대로 보존한다.
  후보의 실제 위치는 별도 source pointer로 제공하되 support를 소급하여 모델 선택으로 기록하지 않는다.
- [ ] E09의 잘못된 인용+잘못된 의미 결합 반례와 정상 Internet Archive·프로젝트명·기술 정보의
  원래 판정 보존을 검증한다. 결과 record 수는 A68/B68, 유실0이어야 한다.
- [ ] GREEN 및 audit 집계 재현(A 인용 결함12/B22)을 확인한 뒤 커밋한다.

## 검토 초점과 종료 조건

- 동일 이름/동일 문장 반복: E03/E07. 첫 등장 자동 선택 금지.
- Unicode·CRLF·HTML: E02/E04. 변환 뒤 offset을 원문 offset처럼 사용하지 않음.
- 부정이 먼 구역에 있는 문서: E08. 근거리 문맥만으로 확정하지 않음.
- 인용 복구가 오확정을 드러내는 경우: E09. 기존 보류 승격0.
- 입력 상한 초과·표 행 귀속: E05/E06/E10. 부분 문맥을 완전하다고 표시하지 않음.

후속 승인으로 이 계획을 실행하더라도 이 단계의 성공은 **위치·추적성 개선**만 뜻한다.
변경된 모델의 정확도·새 confirmed 수치를 생성하지 않는다. 당시 로컬 전체 회귀를 한 번 수행하고 종료한다.
작업 예산 제안: 로컬 구현·검증2시간, 테스트 명령당5분, 실패 원인 수정 뒤에만 재실행.
초과하면 상태를 기록한다. 실제 모델 호출은0으로 고정하며 시간 초과를 이유로 모델 호출로 대체하지 않는다.
