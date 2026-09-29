# 원문 줄 ID 기반 근거 계약 구현 계획

**목표:** 최초 추출에서 모델의 인용·문맥 문자열 생성 과제를 제거하고 서버가 선택된 줄의 정확한 값 위치를 계산한다.

**구조:** `line_evidence.py`가 전용 스키마·근거 투영을 담당한다. `LineEvidenceSolarAnalyzer`는 기존 `RecoverableSolarAnalyzer`의 호출·복구·의미 검토를 재사용하되 최초 추출과 수정 요청의 내부 계약만 바꾼다. 공개 Profile과 기본 서비스 경로는 유지한다.

**대상:** `ai_service/agentfit_ai/line_evidence.py`, `line_evidence_analysis.py`, `solar.py`의 진단 버전 훅, `public_holdout_evaluation.py`의 선택 플래그, 관련 테스트와 이 폴더의 기록.

## 작업 1: 원문 줄 근거 투영

- [ ] 실패 테스트: 유일한 값 span 계산, CRLF·Unicode, 값 부재·중복, 잘못된 줄·역할·상태, 배열 중복, 명시적 없음.
- [ ] `line_schema(line_count)`와 `line_to_profile(document, document_id, fields)`를 최소 구현한다.
- [ ] 관련 테스트를 통과시키고 기존 `evidence-v1` 테스트를 확인한다.

## 작업 2: 선택형 분석기

- [ ] 실패 테스트: 두 최초 호출 및 수정 호출이 줄 ID 계약을 사용하고, 잘못된 후보가 보류되며 기본 payload가 변하지 않는다.
- [ ] 기존 Provider 전송·6회 호출·전체 기한·의미 검토·복구형 질문 흐름을 상속하고 내부 schema/prompt/투영만 교체한다.
- [ ] 안전 진단의 계약 버전을 `line-evidence-v1`으로 표시한다.

## 작업 3: 평가 연결

- [ ] 실패 테스트: 명시적 CLI 플래그만 새 분석기를 선택하고 계획 JSON에 옵션이 기록된다.
- [ ] 기존 공개 평가 CLI에 `--line-evidence`를 추가하고 기본 경로는 불변으로 둔다.
- [ ] 전체 AI 테스트와 실제 `tuning` PRD 5건의 첫 실험을 실행해 결과·한계를 기록한다.
- [ ] feature 브랜치를 push하고 Linux CI를 확인한다.

## 검토 초점

- 같은 값이 한 줄에 두 번 나오면 첫 위치를 자동 선택하지 않는다.
- 줄바꿈 오프셋을 정규화하지 않아 CRLF와 Unicode 위치가 원문과 일치한다.
- 긴 Markdown 표 행에서 모델이 줄 외 문자열을 반환하면 보류한다.
- 비확정 기술을 정확히 인용하더라도 의미 검토 없이 자동 확정하지 않는다.
- 평가의 모델 호출 수·기한·실패 원본 저장 정책이 달라지지 않는다.
