# NVIDIA 단독 서비스 연결 상태

- 전체 목표 active: 입력→분석→사용자 확인/수정→Spring 저장 실사용 완결성. 이전 턴은 NVIDIA-only 엔진95aff76 push/CI36743377541 성공으로 progress.
- 현재 worktree analysis-failure-stages, feature/nvidia-analysis-service. 추적 파일 깨끗함 확인 후 재사용, 기존 HTTP 기준선 테스트 실행. SDD 작성/자기 검토 완료.
- 권한: 목표 내 자율 설계/계획/직접 구현, feature push. 실제 모델0/유료0/배포0. 계정 무료 범위 미확인. Spring 재요청 없이 기존 mock 승인 범위.
- 범위: integrated-nvidia 서비스 모드, 한 키 stdin, 기존 absolute deadline/cancellation, v2→mock 확인 저장. 공개 schema/기본 경로/평가 runner 불변. 독립 평가 variant는 후속.
- 예산: 작업45분 점검/suite180초, 합성기한10초/요청30초/mock45초, cleanup3~5초, 외부0회/0원/재시도0.
- 구현: mode integrated-nvidia→nvidia_only bool→네 문자열 stdin→execute_nvidia_analysis/inline transport→기존 v2. 기본 요청 기한1800/최대3600 적용, key 하나, 기존 모드 보존.
- RED/GREEN: 신규 unit11/11, 기존 worker7/7, 실제 SDK/child/SSE runtime5/5 28.963초, mock core1/1 5.749초. 429/503 1회중단·기한/TCP/ASGI 취소 후 정리·명시적 복구·초안/확인/충돌/삭제 확인. 외부0.
- 다음: 관련 기존 회귀→구현commit→task-done 전체4suite 게이트→독립 최종 리뷰1회→push/CI. 실제 계정/모델/Spring 미검증은 유지.
