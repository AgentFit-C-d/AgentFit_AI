# 독립 최종 리뷰와 수정

## 리뷰

executing-plans의 최종 리뷰1회로 `gpt-6-astra/high`, 새 맥락에서 `8f7de0a..4ca25b4`를 읽기 전용 검토했다. 하위 에이전트·키 읽기·외부 모델 호출·작업 트리 수정은 없었다. Critical0/Important1/Minor0, 판단 유보 목록 없음.

Important: 최종 sidecar에 JSON을 쓴 뒤 fsync 또는 close가 실패해도 정상 분석 stdout을 유지하면서 완전한 JSON 파일이 남았다. 부모는 이를 available/complete로 수락하고 다음 요청을 시작할 수 있었다.

## 한 번의 수정

- fsync/close 오류 주입에서 최종 파일이 남는 두 RED를 직접 확인했다. 부모 실행기에서도 오류 뒤 terminal을 저장하고 다음 문서를 실행하는 RED를 재현했다.
- `.staged` 파일에 독점 기록하고 write/flush/fsync/close가 모두 성공한 뒤 `os.link`로 최종 이름을 게시한다. hard link는 기존 목적지를 덮어쓰지 않는다. staging 자료는 보존한다.
- 정상 stdout은 그대로 유지한다. 부모는 최종 파일 부재를 INVALID_CHECKPOINT로 거절해 다음 호출을 막는다. 기존 staging 파일이 있어도 분석을 시작하지 않는다.
- worker9통과/Windows symlink1skip, probe12통과. write 실패 및 timeout/cancel 검증은 최종 파일 부재와 불완전 staging 보존을 확인하도록 변경했다.
- 전체 회귀 결과는 validation.md에 기록한다. 재리뷰 없이 회귀로 수정 여부를 판정한다.

## 판단 기록

1. 사용자의 자율 SDD·직접 실행 승인에 따라 기존 설계를 반복 승인받지 않았다. 오판 비용은 되돌릴 수 있는 선택형 진단 변경이며 공개 API와 분석 알고리즘은 그대로다.
2. 변경 전 기준선의 기존1244통과/5skip·CI 증거를 재사용하고 새 기능의 전체 회귀를 별도로 실행했다. 환경 변화는 새 검증에서 탐지한다.
3. worktree와 .superpowers를 보존하며 feature commit/push만 한다. 비용은 로컬 보관 공간이다.
4. 부모가 중복 구현하지 않도록 validate_probe_report를 추가하고 worker를 명시적 DeepSeek 진단 요청으로 한정했다. 다른 모드 진단은 거절되지만 기본 worker는 그대로다.
5. 이번 단발 진단은 기존 출력 디렉터리를 모두 거절하며 재개/재시작하지 않는다. 후속 별도 실험에는 새 디렉터리가 필요하다.
6. 최종 파일 게시에 hard link를 사용한다. 지원하지 않는 파일 시스템은 분석 stdout을 유지하지만 진단이 실패한다. 현재 Windows·Linux 테스트/CI로 지원 여부를 확인하며 유료 재시도는 없다.

보류한 Minor 지적은 없다. 코드 리뷰·테스트는 실제 분석 품질 또는 운영 배포 승인을 뜻하지 않는다.
