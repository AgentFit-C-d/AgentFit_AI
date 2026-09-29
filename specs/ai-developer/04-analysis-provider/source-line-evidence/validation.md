# 원문 줄 ID 기반 근거 계약 검증 기록

## 구현 전 근거

- 고정 공개 PRD 5건의 첫 평가에서 Solar 기본 구성과 문맥·병렬 구성 모두 자동 완료 0건이었다. 안전 진단에서 최초 core 또는 features의 `QUOTE_NOT_FOUND`·`QUOTE_NOT_IN_CONTEXT`·`VALUE_NOT_IN_QUOTE`가 반복됐다.
- 기존 `repair-context-options`는 첫 추출 이후 수정 요청에만 선택지를 제공한다. 이 실험은 최초 추출부터 quote/context 생성 필드를 제거한다.

## 로컬 구현 확인

- opt-in `LineEvidenceSolarAnalyzer`는 core, features, 수정 요청에 `{value,lineId,role}`을 사용한다. 서버가 선택한 줄에서 정확 값의 유일한 위치를 구하며, 없음·중복·줄 ID·역할·상태 오류를 거부한다.
- Profile 반환 구조·의미 검토·기존 복구형 확인 질문 경로를 유지한다. 기본 `SolarAnalyzer`의 스키마는 변경하지 않았다.
- 단위·모의 Provider 테스트에서는 CRLF·Unicode 위치, 반복 문자열 거부, 명시적 없음, 오류 필드 수정, 실패 초안 보존, 안전 진단 버전·오류 코드, CLI opt-in을 확인했다.
- `python -m unittest discover -s tests -q`: 로컬 599건 통과. 기본 `SolarAnalyzer`의 기존 JSON 근거 스키마를 유지하고, 새 CLI 플래그에서만 줄 ID 분석기를 선택함을 테스트했다.

## 공개 PRD 튜닝 실험

- `public-prd-holdout/manifest.json`의 이미 사용한 PRD 5건을 `partition=tuning`으로 실행했다. 모델은 `solar-pro4`, 기본 첫 추출 순서, 근거·의미 검토 사용, 분석 기한 40초였다. `--line-evidence`만 추가했다. 산출물은 ignored 로컬 `tmp/public-prd-line-evidence-20260929/`에 있으며 plan의 `line_evidence=true`·manifest SHA-256 `6a508a376e9113a855eb956752c32778ac2f24e2cbecf9d821e3d925ff44b338`을 확인했다.
- 자동 완료 0, 확인 필요 4, 실패 1. 채점 가능 4건의 양성 점검 26개 중 일치 11, 누락 9, 근거 판정 불가 6, 확정 근거 오류 0이었다. 명시적 미정 4개 중 `null` 유지 2, 비 `null` 제안 2였다. 정답 밖 값 17개는 평가하지 않았다. Price.kr는 기능 추출 Provider 기한으로 초안 없이 실패했다.
- DeReel·TrueTwo·Campfire는 최초 features에서 `VALUE_NOT_IN_LINE`이 났고 수정 후에도 남았다. Gongsi-MCP는 최초 core의 domain/deployment/external_integrations에 같은 오류가 났으며 수정은 구조 검증을 통과했지만 의미 검토 호출이 40초 기한을 소진했다. 최초 core 검증 성공은 Campfire 1건, 최초 features 성공은 Gongsi-MCP 1건뿐이다. 최대 4회 호출, 최장 40,086ms였다.
- 앞선 기본 Solar의 독립 첫 실행은 0/5/0, 일치 11/35·누락 21·판정 불가 3이었다. 이번 것은 별도 확률적 응답이자 튜닝 자료 재사용이고 Price.kr 미채점으로 분모도 다르다. 일치 11이나 누락 9를 개선량으로 해석하지 않는다. 구조 오류가 `QUOTE_NOT_FOUND`에서 `VALUE_NOT_IN_LINE`으로 이동했으며 완전한 결과는 만들지 못했다.
- JSON 3개에 API 키와 5개 전체 원문이 포함되지 않음을 확인했다. SHA-256은 plan `b4eac162f596b43a41f59469c32e7c735558783b6846f95b70db905418498724`, results `0e3394a928c013e1c689d184e0b4b3944e1354dd58af995923ff1f136dc9213e`, summary `16a64154e5c995cae0ce845d47d7f9775c94111455845c8976be075b53391996`이다.

## 결정

- 운영 기본값으로 전환하지 않는다. 줄 ID만 서버가 고정해도 모델의 값 복사 오류와 40초 기한 문제가 남는다. 다음에는 값 문자열까지 서버가 만든 후보에서 ID로 선택하게 하고, 위치·역할·확정성 검증은 유지하는 방식을 검토한다.
- 구현 커밋 `e58d053`과 결과 커밋 `5c33d4e`를 `feature/source-line-evidence`에 push했다. 로컬 전체 AI 테스트 599건과 최신 Linux CI 실행 36530489896이 성공했다. CI 통과는 실제 PRD 품질 달성이나 배포 완료를 의미하지 않는다.

## 미해결

- 모델이 정확한 `value`조차 복사하지 못하면 `VALUE_NOT_IN_LINE`으로 보류된다. 구조적 오류 감소나 의미 정확도 개선은 실제 PRD 튜닝 실행 전에는 입증되지 않는다.
- 원문 줄 전체를 의미 검토에 제공하지만 Profile 근거 span은 값 자체의 위치다. 상태를 나타내는 주변 문맥의 해석은 의미 검토 결과에 의존한다.
- 새 독립 문서, 실제 사용자 확인 부담, Spring/Frontend 저장 E2E는 별도 검증이 필요하다.
