# 검토 계약 오류 진단 상태

## 목표·권한

- 전체 실사용 목표 active. 설계·계획·구현 자율 승인, SDD·직접 구현·기능별 feature push 유지.
- 진단 구현 전 상태 보고 턴은 no progress였고 이후 구현 턴은 progress였다. 이번 재개는 clean15adc6c와 실제 살아 있는 session56367을 확인했다.
- checkout E:/AgentFit/tmp/worktrees/integrated-input-guard 재사용. branch feature/review-contract-diagnostics, base e5446502562a8ac5452f740e73fb6675e63ecdfc.

## 현재

- 명세·계획 commit4f4cfcf. 구현06d1e04242f260abdfa40724f8ffd242ee14bf33, Task1 완료. 독립 리뷰 Critical0/Important0/Minor0, 신규7테스트 리뷰어 재실행 통과. 수락 조건을 완화하지 않고 실패 원인 관측만 추가.
- 기준989/983pass6skip. 신규7테스트 RED49실패→GREEN7/7. 전체996/990pass6skip,19.552초/exit0. API0.
- 변경 파일: candidate_split_review.py, test_review_contract_diagnostics.py 및 본 기능spec/plan/validation/STATE.
- 실제 GLM5번째 검토의 정확한 원인은 아직 미확인. 과거 원문 응답은 보관하지 않아 복원하지 않는다.
- Task1 최종996건/990pass6skip,19.616초/exit0. feature/review-contract-diagnostics push 완료. 정확한06d1e04의 CI36674103301 completed/success, 의존성호환·실제LinuxPDF메모리·전체suite 단계 통과.
- 새H02 실제평가 session56367/PID36160은10호출 반환 후11번째 GLM 검토 진행을 도구에서 확인했다. 드라이버·보고서는 E:/AgentFit/tmp/review-contract-h02-20260930-v1.py 및 .json, 감사는 audit-review-contract-h02-20260930-v1.py. 합성 드라이버3/3·preflight API0 통과. revision06d1e04 고정. 살아 있는 동안 이 checkout의 제품 코드를 변경하지 않는다.
- 다음: 같은 session56367을 poll한다. 종료 후 안전 감사와 contract_issue enum만 확인한다. 관측 timeout을 종료로 오인하거나 재시작하지 않는다. 이 진행 checkpoint를 commit/push하고, 실측 결과는 종료 후 추가 기록한다.
- 이번 목표 턴은 progress: 진단 기능 구현·검증·독립 리뷰·push/CI 완료, 새 실측 시작. 전체 목표 완료 아님.
- 후속 재개 중 structured-output-findings.md에 공식 문서 조사와 현재 schema/predicate 경계를 기록했다. 현재 schema가 checked-ID 순서·wrong-ID 중복·reason ID 일대일 연결을 표현하지 않는 사실을 확인했다. 이는 실제 실패 원인의 단정이 아니며 제품·드라이버는 변경하지 않았다.
- 실제 session56367은분류완료: grounded204/rejected7, confirmed112/tentative21/irrelevant48/negated23. 11번째 GLM 검토 진행 중, 최근50초poll은새출력없음/세션live. 관측 timeout이므로 종료나 재시작 근거가 아니다.
- 별도 합성 형식 spike session82995는exit0종료, json_schema/guided_json 각1호출 모두 enum준수. E:/AgentFit/tmp/probe-glm-structured-format-20260930.py/.json, code_unchanged=true. 문서·개인정보 전송 없음. H02시간은 순수지연비교에서 제외한다. 종료한 probe를 재시작하지 말고 session56367만 계속 관측한다.
- 후속 목표 턴은 progress+verified wait: 실제2호출의 형식 실험과 공식문서/기존계약 조사로 설정 변경을 지지하는 근거가 없음을 확인했고 aacba7f까지push했다. 전체 모델 품질 완료 아님. 현재 추출 후보 수가 이전195와다른204이므로 어떤 점수 변화도 진단 코드의 개선 효과로 인과 주장하지 않는다.

## 경계

- 원문/파생 발췌 표시 승인 및 Spring 위치 질문은 답변 대기. 새 평가에서는 기존 승인된 개인정보 제거 API 전송만 수행하고 내용은 출력하지 않는다.
- 실사용 완료는 모델 품질·확인/저장·Spring 연동·실패 원본 7일 만료 등 근거가 더 필요하다.

## 최신 종료·인계 — 2026-09-30

- session56367은 exit1 종료. 재시작 금지. 총17호출/2,730,631ms, 감사18항목 모두true, code_unchanged=true. 1~5번째 후보 검토 계약은 통과했으나 6번째12개 묶음에서 NVIDIA PROVIDER_UNAVAILABLE가 최초·재시도 모두 발생했다(호출16/17, 각약302.5초).
- 결과 complete0/needs_confirmation0/failed1, error COVERAGE_REVIEW_FAILED, provider_error PROVIDER_UNAVAILABLE. 부분정답6개 전부 미평가. review_contract_issues 없음은 마지막 전송 실패의 해결을 의미하지 않는다. 이번 실행은 모델 품질 개선을 입증하지 못했다.
- 사용자에게 마지막 묶음 완료/전체 누락 검사 진입이라고 알린 중간 설명을 정정했다. 다음 호출 시작은 재시도일 수 있으므로 단계 판정에 trace의 attempt/retry 링크와 review_calls stage를 함께 사용한다.
- 사용자 최신 요청: 이번 결과를 포함해 AI 개발 전체 진행도를 %로 보고. AI 전체 후속 기능(Capability/추천 설명/자연어 Skill)과 현재 문서 분석의 실사용 준비도를 구분하고, %는 요구사항 대비 추정이며 테스트 통과율/모델 정확도가 아님을 명시한다.
- 독립 후속 작업용 E:/AgentFit/tmp/worktrees/analysis-runtime, feature/integrated-analysis-runtime, base aacba7ff348e929aaa1a9a4b8300b40be1099527를 이전 재개에서 만들었다. native worktree 생성은 소유권 오류로 실패해 exact safe.directory의 수동 대안을 사용했다. 아직 명세·계획·구현·설치 없음. 런타임은 실제 실험에 쓰인 langextract1.7.0의 선택형 requirements, 깨끗한 설치, 실제 SDK 기본 추출 경로의 합성 transport 검증과 CI가 필요하다. 공유 venv를 변경하지 않는다.
- 다음은 제공자 실패를 의미 품질과 구분해 기록한 상태에서 선택형 런타임 패키징 및 서비스 연결 과제를 진행한다. 실제 API 재평가는 가설과 검증 범위를 정한 뒤 수행한다. Spring 위치·개인 문서 발췌 표시 승인은 여전히 대기 중. 전체 목표 active/미완료.
