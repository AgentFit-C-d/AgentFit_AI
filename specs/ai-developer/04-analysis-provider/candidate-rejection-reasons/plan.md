# 후보 탈락 사유 계약 구현 계획

> **For agentic workers:** superpowers:executing-plans로 직접 구현하고 마지막에 독립 리뷰한다. 기존 사용자 자율 진행 승인을 적용한다.

**Goal:** 검토 탈락의 이유를 검증 가능한 코드 계약으로 받아 진단하고 실제 정보 손실 변화를 측정한다.
**Architecture:** 기존 candidate_split_review의 후보 묶음에만 opt-in 사유 schema·검증·수집기를 추가한다. 외부 반환 및 최종 Profile 변환은 그대로 사용한다.
**Tech Stack:** Python unittest, 기존 Solar/NVIDIA adapter.
**Spec:** [spec.md](spec.md).

## Global Constraints

False 요청 불변. 최대20후보/묶음, 사유4종, 추가 호출 없음. 기본 HTTP 미연결. 실제 원문/키/응답 저장 금지. 기존 clean dcc44ac에서 feature/candidate-rejection-reasons 분기. 실행 종료된 worktree를 재사용한다.

## Review Focus

1. 잘못된 타입·배열·추가 키가 정상 검토로 바뀌지 않는가.
2. 사유와 탈락 ID의 누락/중복/다른 묶음 ID가 매핑되지 않는가.
3. 뒤 묶음 실패에서 앞 기록은 남고 Profile 생성은 중단되는가.
4. 기본 요청 및 NVIDIA/Solar 모델 검증이 유지되는가.
5. 실험 지표 개선이 의미 정확성이나 기본 서비스 승격으로 오해되지 않는가.

## Task 1: 사유 응답 계약과 수집

**Files:** ai_service/agentfit_ai/candidate_split_review.py, ai_service/tests/test_candidate_rejection_reasons.py.
**Interfaces:** 소비: 기존 review_candidates_separately/document/frozen/labels. 생산: 추가 키워드 reasoned_review: bool=False, review_reasons: list|None=None; 반환은 기존 checkedFields/missingFields/wrongCandidateIds만.

- [x] 테스트 작성: supported 후보 유지/탈락 후보 제외, 사유 순서 독립,20+1 묶음, 모드False 요청 동일, 비밀 없는 수집기,7종 이상 malformed 사유 실패, 입력 설정 실패 시 호출0, 뒤 묶음 실패 시 부분 기록만 유지.
- [x] `python -m unittest discover -s tests -p test_candidate_rejection_reasons.py -v`로 RED 확인. 새 키워드 미지원이 실패 원인이어야 한다.
- [x] _payload의 기존 schema를 True일 때만 확장하고 정확한 일대일 검증 후 사유 복사. 커버리지 payload는 그대로 둔다.
- [x] 위 테스트와 split/adaptive/routing 관련 테스트 GREEN, 전체 `python -m unittest discover -s tests -v` 확인 후 커밋.

## Task 2: 고정 후보 비교·최종 검증

- [x] 승인된 H02 원문/해시와 operation-candidates 결과의 merged_refs로 동일183개 후보를 복원한다. 로컬 비교 driver에서 각 모드의 원문/후보/분류/모델 설정을 고정하고 서로 독립된 복사본을 사용한다.
- [x] 독립 리뷰1회, 중요 발견만 RED→GREEN 수정1패스 및 전체 테스트, feature 브랜치 push·CI 확인.
- [x] 새 결과 파일로 기존/사유 모드 비교. PID/시작/종료를 추적하고 코드·집계·위치만 저장한다. 실제 원문 문맥으로 잘못된 유지와 탈락을 대조한다. 코드와 문서 최종 상태를 commit/push한다.

## 기록

- Pre-flight: Task2는 Task1의 선택형 키워드와 수집기만 소비하며 기존 반환 계약은 그대로다. 충돌 없음.
- 기준877검사871통과·6skip 및 CI dcee55d 성공. 직전 변화는 문서만이다.
- 사유의 언어 모델 판단은 검증기가 의미까지 증명하지 못한다. 실제 문서·반복 검증을 완료 조건으로 유지한다.
- 구현2063f0b, 전체885건879pass6skip. 독립 리뷰 수정 사항 없음, 별도 신규8+기존19 테스트 및 모델/복구 경계 확인. CI36636710843 success.
- 실제 짝 비교 종료: 동일183개 후보, 각7호출, 기존/사유 모두 지정6/6·needs_confirmation. 사유 모드는 인증 API를 유지하고 일부 잘못된 외부 연동과 기대효과를 제거했지만 명시적 동작도 잃었다. 다른 실행의 기존 모드에서는 같은 API가 제외됐으므로 안정적인 개선 효과는 미확인이다.
- 전체 목표 미완료: 사유를 바꾸는 것만으로 서비스 품질을 확보하지 못했다. 다음 조사 대상은 모델간 동일 판정 단위의 안정성, 탈락을 확정적 무관 정보로 변환하는 정책, 근거 없이 누락 필드를 지목하는 커버리지 계약이다. 기본 서비스 승격은 하지 않는다.
