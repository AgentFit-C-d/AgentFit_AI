# 원문 프로젝트명 표현 보존 검증

## 결과

- 같은 원문 위치에서 확정된 두 표기가 실제 괄호 표현을 이루면 원문 전체와 근거 구간을 보존한다. 이름은 계속 확인 필요이며 자동 완료하지 않는다.
- 양언어·순서·전각 괄호·공백·Unicode 위치·세 번째 이름·미확정/다른 위치 예시·길이 제한과 안전한 비교 진단을 새9개 테스트로 검증했다. 관련35건 통과.
- 전체857건 실행,851건 통과·6건 건너뜀, 종료 코드0. 처음 실패한 기존 CRLF 테스트2건은 입력 정규화 후 재실행해 통과했다. 로더나 고정 평가 데이터의 해시는 바꾸지 않았다.
- 독립 리뷰에서 Critical/Important/Minor 지적 없음. 리뷰어가 관련26건·CRLF2건과 추가 경계4건을 확인했다.
- 리뷰 보류 항목 판정: 두 이름의 의미적 동등성은 이 코드가 확정하지 않는다. private H02 재생은 메인에서 직접 확인했다. 전체 모델 품질은 미완료이며 Linux CI는 push 후 확인한다.

## 실제 문서의 고정 후보 재생

- 입력: 종료된 candidate-paired-review H02의 reviewed_refs. 원본 SHA256 `2a290fff891ac850a03ea715629a8d9fef1fb1628776eec8e852c8175b2bb24d`, 비식별 추출 SHA256 `edb8447e18f9a8d29523ea7beb3f9aa76d78624414db2b7d80d88b1969b75b99` 확인.
- 승인 manifest의 LF 정규화 SHA256 `a69837761609613a5252e6014f85d996681ef54c2c0938a68fdb9208deb0db95`를 확인했다.
- 이전 b63cac9 코드와 수정 코드를 동일 후보에서 각각 실행했다. coverage_verified=false인 **변환 단계만의 재생**이며 모델 호출·커버리지 검토를 새로 실행하지 않았다. 원문이나 Profile 값은 결과 파일에 저장하지 않았다.

| 검토 후보 출처 | 이전 지정 검사 | 수정 후 지정 검사 | 이름 근거 | 결과 |
|---|---:|---:|---|---|
| Solar Pro4 | 4/6 | 5/6 | 전체 원문 표현과 정확히 일치 | 확인 필요 유지 |
| DeepSeek V4.1 Flash | 5/6 | 6/6 | 전체 원문 표현과 정확히 일치 | 확인 필요 유지 |

나머지9필드의 값·근거를 합친 SHA256은 전후 동일했다. Solar는 `5b76c54fce73ff0ca9192c10b20ccd9e8da4fd24dbba859676ea5e866006b776`, DeepSeek는 `c397749cf35a537ee6bdae3ccfb14fa971c504001925f768b8141a73bcd492e3`이다.

로컬 비공개 재생 도구/안전 집계: `E:/AgentFit/tmp/replay-source-name-projection.py`, `source-name-replay-old.json`, `source-name-replay-new.json`. 전체 검사 로그는 `E:/AgentFit/tmp/source-name-full-tests.log`다.

## 한계와 다음 작업

- 한 튜닝 문서의 희소한6개 검사이며 전체 정확도·재현율·독립 문서 일반화를 입증하지 않는다. 6/6을 실사용 완료로 해석하지 않는다.
- DeepSeek가 삭제한 기능에는 실제 기능을 가리키는 명사구, 미래 단계 기능, 필드 분류가 모호한 대상이 섞여 있다. project_type의 확정 웹 대시보드 두 후보도 제외됐다. 모델 교체 전 역할·시간 범위·추출 구간의 완전성을 분리해서 평가해야 한다.
- 기본 서비스 경로·공개 Profile은 유지했고 이 실험은 아직 HTTP 경로에 연결하지 않았다. 실제 Spring 확인·수정·최종 저장 연동 검증은 남아 있다.
- 모델 비교 결과 문서는 candidate-paired-review/validation.md를 함께 참고한다.

## 배포 전 확인

- 코드2620207 및 비교 결과 문서c338659를 `feature/source-name-expressions`에 push했다. [c338659의 Linux CI36630464051](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36630464051) success를 확인했다.
- 실사용 목표: active. 이 기능 완료와 전체 목표 완료를 구분한다.
