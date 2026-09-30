# 전체 경로 비교 사전 등록

## 실행 전 gate

구현·리뷰 수정 후 로컬1294통과/6skip, 최종 독립 리뷰, 중요 수정 검증, branch push 및 해당 코드 CI 성공을 확인한 뒤에만 실행한다. 별도 `freeze.json`은 최종 코드에서 생성하며 이전 freeze는 수정하지 않는다.

## 고정 조건

- 기존 공개 PUBLIC-01, PUBLIC-09, PUBLIC-07 각1회. 기존 문서/임시 gold/DeepSeek 추출·분류·검토·기능 모델/기타 설정 유지.
- 변경: `capability_candidates=True`, quote-only 기능 후보 + 정확 인용의 모든 등장 위치. 일반 추출→merge→explicit-v1 분류→검토→대표 기능→Profile의 전체 경로를 수행한다.
- 전체 최대192모델호출/5400초, 요청64호출/1800초, 재시도0. 기존 무료 확인 기록을 그대로 검증하고 만료/한도/제공자 오류 시 중단. 새로운 유료 호출/개인 문서 전송/배포 없음.
- 새 출력 `E:/AgentFit/output/independent-profile-v1/capability-occurrences-full-v1`만 사용. 기존 실행/출력은 재개하거나 덮어쓰지 않는다.

## 실행기와 증거

이미 검증한 `diagnostic_tools.candidate_trace_probe`와 disposable worker를 재사용한다. 이 계획 scratch의 `live_probe.py`가 worker의 내부 분석 호출에 bool 옵션만 지정한다. 기본 서비스 프로세스에는 적용하지 않는다. manifest에 `version=capability-occurrences-probe-v1`, 실제 옵션, wrapper hash, 도구 hash, 원래 평가 metadata를 함께 기록하고 매 요청 전후 재검증한다.

키/원문/원본 응답을 추가 결과에 저장하지 않는다. 기존 sidecar의 단계별 후보 ID·위치·분류 enum·거절 수·확인 필요 상태를 엄격 검증한다. 임시 gold는 부모의 채점 과정에만 사용한다.

## 판정

직전 전체 진단의 PUBLIC-01 0/7,09 0/3,07 11/11 기능 후보 위치 도달과 비교한다. 기능 위치 도달·분류/검토 손실·Profile 보류를 각각 보고한다. 도달 증가만으로 오확정 감소나 의미 정확도 향상을 주장하지 않는다. Pro 안내·기술 용도·당위형 문장은 별도 의미 검토 대상으로 유지한다. 한 번씩의 결과는 반복 안정성과 새 문서 일반화의 증거가 아니다.

기능 후보가 늘어도240상한/확인 부담/기타 필드 손실이 악화되면 기본 서비스 적용을 보류한다. 사람이 검토한 새 기획서 품질·수정량/시간·실제 Spring/운영 gate는 유지한다.
