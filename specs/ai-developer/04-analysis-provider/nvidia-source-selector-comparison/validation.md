# NVIDIA 원문 선택자 전체 분석 비교 기록

## 구현과 로컬 검증

- 선택형 `NvidiaSourceSelectorAnalyzer`가 기존 원문 선택자 추출·수정·의미 검토의 모든 요청을 `NvidiaAnalyzer`로 보낸다. 지원 NIM 모델명·반환 모델명·JSON 응답을 검증한다. NVIDIA 어댑터의 임시 전송 교체가 병렬 호출과 충돌할 수 있어 선택형 병렬 최초 추출은 거부한다.
- 평가 CLI는 `--source-selector-model`에 따라 NVIDIA/Upstage 키와 전송 함수를 분리한다. 실험용 `--accuracy-first`는 전체 300초·필드 호출 120초를 허용한다. 기본 서비스의 전체 60초·필드 40초·의미 검토 8,192토큰은 유지한다. 최대 6회 호출과 공개 Profile도 불변이다.
- `python -m unittest discover -s tests -q`는 최종 로컬 617건 통과했다. 숫자형 토큰 진단은 원본 응답·문서·키를 저장하지 않는 테스트를 포함한다.
- 합성 문서 `# Cedar / 상품 검색`의 DeepSeek 전체 경로는 `complete`를 반환했고 약 133,483ms가 걸렸다. 이는 1건의 호환성 검사다.

## 이미 튜닝에 쓴 공개 PRD 5건, 긴 기한

두 모델 모두 같은 원문 선택자 계약·부분 정답 35개·전체 300초·필드 호출 120초·의미 검토 8,192토큰으로 각 문서를 1회 분석했다. 서로 다른 확률적 추출·검토 응답이므로 수치 차이를 모델만의 인과 효과로 해석하지 않는다.

| 지표 | Solar Pro4 | DeepSeek V4.1 Flash |
|---|---:|---:|
| 자동 완료 / 확인 필요 / 실패 | 0 / 5 / 0 | 0 / 5 / 0 |
| 부분 정답 일치 / 누락 / 판정 불가 | 11 / 5 / 19 | 8 / 21 / 6 |
| 확정 근거 오류 | 0 | 0 |
| 정답 밖 값(미평가) | 118 | 46 |
| 명시적 미정 null 유지 / 비 null | 4 / 1 | 5 / 0 |
| 최대 Provider 호출 / 최장 경과 | 4 / 114,001ms | 5 / 249,532ms |

- Solar는 DeReel·Campfire·Price.kr의 의미 검토에서 `INCOMPLETE_RESPONSE`, TrueTwo·Gongsi의 선택자 값 길이/중복 근거 검증에서 실패했다. DeepSeek는 DeReel·TrueTwo의 의미 수정, Gongsi·Price.kr의 구조 수정, Campfire의 의미 검토 형식 검증에서 실패했다. 어느 쪽도 운영 기본값 후보가 아니다.
- DeepSeek 합성 호환성 성공은 실제 문서의 완전성 근거가 아니었다. 기존 40초 Solar 선택자 결과 역시 자동 완료 0/5였지만 별도 응답·다른 기한이다.

## 의미 검토 출력 한도 진단

- Campfire만 숫자형 토큰 추적을 추가해 Solar/8,192토큰으로 재실행했다. core·features는 검증 통과, 의미 검토는 `completion_tokens=8192`, `max_tokens=8192`, `INCOMPLETE_RESPONSE`였다. 출력 상한 도달을 이 재실행에서 확인했다.
- 평가 전용 의미 검토 한도를 16,384로 늘린 Campfire 재실행에서는 core·features가 검증 통과했지만 의미 검토가 약 276,136ms 후 `PROVIDER_TIMEOUT`이 됐고 전체 300,076ms에 `needs_confirmation`이었다. 출력 토큰 사용량은 응답이 없어 미확인이다. 한도 확대만으로는 자동 완료를 얻지 못했다.
- 이 재실행들은 최초와 다른 모델 응답이므로 수치의 전후 개선량으로 해석하지 않는다. 다음에는 검토 응답을 더 작게 만드는 계약 또는 검토 범위 분할을 설계해야 한다.

## 산출물·남은 문제

- ignored 로컬 `tmp/public-prd-nvidia-selector-20260929`, `tmp/public-prd-solar-selector-long-20260929`, `tmp/public-prd-solar-selector-token-probe-20260929`, `tmp/public-prd-solar-selector-review16k-20260929`에 안전한 plan/results/summary만 남겼다. 네 묶음 모두 실제 NVIDIA·Upstage 키와 문서 전체 원문이 결과 JSON에 없음을 확인했다.
- `plan/results/summary` SHA-256: DeepSeek `588299e4/ c58f8ff4/79f222d0`, Solar 긴 기한 `abb1efc1/87da5224/6b2899cb`, 8K 원인 조사 `6ee8e412/6e2c05c0/cd4ae337`, 16K 시험 `291fe453/f1af906e/b402325d` (각 해시 앞 8자리).
- 새 독립 실제 문서, 정답 밖 값의 사람 검토, 사용자 확인 후 Spring 저장 금지 E2E는 여전히 미검증이다.
