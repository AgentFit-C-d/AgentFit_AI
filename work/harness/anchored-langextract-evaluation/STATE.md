# 상태

- 상위 목표: AgentFit AI 분석을 실사용 가능한 수준으로 검증·개선한다. NVIDIA preview 모델 사용과 목표 범위의 계획·구현은 사용자 승인됨.
- 현재 기능: 반복 문구의 근거 위치를 LangExtract `candidate_attributes.anchor`로 선택형 평가한다. 기본 서비스·공개 Profile은 유지한다.
- 기준: `feature/document-grounding-evaluation`의 합성 18건에서 실패 3, 허용 누락 7, 근거 위치 일치 2, 자동 오확정 관측 0. 실제 문서 일반화·서비스 통합은 미검증.
- 2026-09-29: 기존 linked worktree `E:/AgentFit/tmp/worktrees/paired-review-evaluation` 재사용, 기준 테스트 729건 통과. `feature/anchored-langextract-evaluation` 생성. 명세·계획 작성.
- 다음 행동: 속성 파싱 계약을 작은 합성 probe로 확인한 뒤 Task 1부터 테스트 우선 구현한다. 원문·키·모델 응답은 영속 기록하지 않는다.
- Ruling: `sdd-workspace` Bash 스크립트는 이 Windows 환경에서 `/bin/bash` 부재로 실행되지 않았다. 프로젝트 `work/harness/anchored-langextract-evaluation/STATE.md`를 실행 원장으로 쓴다. 비용: 스킬 전용 임시 산출물 자동 정리는 사용하지 못한다.
- Task 1: 합성 고정 모델로 LangExtract 1.7.0의 anchor 속성 파싱을 확인했다. 문맥 정확·고유성 및 중복 최종 위치 검증 테스트가 구현 전 실패, 구현 후 10/10 통과했다. 전체 서비스 테스트 739/739 통과.
- 다음 행동: Task 2의 Solar 스키마·LangExtract 속성 연결을 테스트 우선으로 구현한다.
- Task 2: 필수 `candidate_attributes.anchor` 응답 스키마와 한국어 반복 예시를 연결했다. 이전 테스트 더블은 빈 위치를 `SimpleNamespace(None,None)`로 만들어 실제 LangExtract의 `char_interval=None`과 달랐으므로 실측 형식에 맞춰 고쳤다. 새 계약 테스트는 기대한 실패 후 통과했고 전체 741/741 통과.
- 다음 행동: Task 3에서 같은 원문의 짝 사례를 한 번만 추출하도록 바꾸고 합성 18건을 실측한다.
- Task 3: 18건의 짝 문서는 문서당 한 번 추출해 15회 호출한다. 같은 원문의 실패를 두 행에 전파하고 원문·인용·키는 안전 결과에서 제외했다. 첫 실행은 실패 0·허용 누락 5·골드 근거 8/18이었다.
- Ruling: 실제 LangExtract의 `MATCH_LESSER`는 후보의 일부 위치만 반환한다. 원문에서 고유한 anchor와 그 안의 정확 후보가 서버에 의해 검증되면 부분 정렬 위치를 무시한다. `MATCH_EXACT` 충돌은 유지한다. 비용: 모델이 잘못된 고유 문맥을 복사해도 그 문맥에 실제 후보가 있다면 해당 실제 위치를 평가하게 된다.
- 원인 확인: 허용 누락 5건 중 4건은 후보 문자열이 골드와 같고 라이브러리가 `MATCH_LESSER`(시작 동일, 끝 3자 짧음)를 반환했다. 예시의 한국어 조사 붙은 이름은 prompt validation 경고로 로그에 출력됐다. 영문 토큰 경계 예시로 교체하고 별도 실제 파서 테스트를 통과했다.
- 최종 합성 설정 18/18, 실패 0, 오확정 0, 허용 누락 0, 근거 위치 18/18. 동일 설정 재실행도 18/18. 튜닝셋이므로 실사용 판정은 보류한다.
- 다음 행동: 전체 테스트·CI·독립 리뷰 후 branch push. 이어서 독립 사례와 실제 문서 평가로 일반화 여부를 확인한다.
- 최종 코드 기준 로컬 전체 745/745 통과(선택형 실제 파서 1건 skip), 실험 venv 실제 파서 15/15 통과, `git diff --check` 통과.
- `8dec3b4` push 후 Linux CI `36579794117` 성공. 독립 리뷰가 중복 anchor의 오확정(P1)과 서로 다른 anchor의 과잉 보류(P2)를 재현했다. 두 회귀 테스트를 먼저 실패시킨 뒤 검증된 원문 위치로 중복 검사하도록 수정했다.
- 수정 후 전체 로컬 748건 통과(1 skip), 실험 venv 17건 통과, 합성 라이브 18/18·오확정 0·허용 누락 0·제공자 호출 15회. 최종 CI 확인과 push가 남았다. 이 사례는 튜닝셋이므로 서비스 일반화 근거가 아니다.
