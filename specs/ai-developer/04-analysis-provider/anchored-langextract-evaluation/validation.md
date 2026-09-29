# 문맥 인용 기반 LangExtract 평가 결과

## 범위

- 기존 고정 합성 골드 18건(반복 6, 부정 6, 검토안 6)을 수정하지 않았다. SHA-256 검증 후 `--live`로만 Solar에 전송했다.
- 같은 원문을 공유한 짝은 한 번 추출해 함께 채점했다. 최종 실행의 원문별 제공자 호출은 15회였다.
- LangExtract 1.7.0의 실제 파서는 `candidate_attributes.anchor`를 `Extraction.attributes`에 전달했다. 후보의 정확 문자열·고유 문맥과 중복·충돌을 서버가 검증했다. 기본 FastAPI·Profile·PDF worker에는 적용하지 않았다.

## 측정

| 선택형 설정 | 완료/18 | 호출 실패 | 자동 오확정 | 허용 누락 | 골드 근거 위치 일치 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 이전 안전 설정, 문구만 추출 | 15 | 3 | 0 | 7 | 2 |
| 후보별 고유 문맥, 부분 정렬 충돌 유지 | 18 | 0 | 0 | 5 | 8 |
| 고유 문맥으로 `MATCH_LESSER` 복구 | 18 | 0 | 0 | 0 | 18 |
| 같은 최종 설정 재실행 | 18 | 0 | 0 | 0 | 18 |

- 안전 결과 파일: `E:/AgentFit/tmp/langextract-anchor-adversarial-20260929-1.json`, `E:/AgentFit/tmp/langextract-anchor-adversarial-20260929-partial-2.json`, `E:/AgentFit/tmp/langextract-anchor-adversarial-20260929-final-3.json`. 결과에는 원문·후보·문맥·API 키·모델 원본 응답을 쓰지 않았다.
- 처음 남은 5개 허용 누락 중 4건의 모델 후보 문자열은 골드와 같았지만 LangExtract가 일부 문자만 `MATCH_LESSER`로 표시했다. 고유한 원문 문맥과 정확 인용이 독립적으로 확인될 때만 이 부분 위치를 무시했다. `MATCH_EXACT`의 충돌은 여전히 보류한다. 한 사례는 재호출에서 후보 수가 달라져 개별 호출의 변동을 확인했다.
- 한국어 조사에 붙은 예시 후보가 LangExtract의 prompt alignment 경고에 인용문으로 출력되는 현상을 재현했다. 토큰 경계가 맞는 영문 합성 예시로 교체한 뒤 실제 LangExtract 파서 테스트에서 예시 경고가 사라졌다. 최종 18건 실행에도 해당 경고가 없었다.

## 해석과 남은 검증

- 이 18건은 설계와 디버깅에 사용한 **튜닝셋**이다. 18/18은 실사용 성능이나 새로운 문서로의 일반화를 입증하지 않는다. 독립적인 사례, 길고 복잡한 실제 문서, 기본 분석기 비교 및 Spring 연동 평가가 남았다.
- Docling 구조 분석과 LangExtract 경로의 통합도 아직 실험되지 않았다. 기존 Docling native PDF 실험은 텍스트·페이지 위치만 확인했다.
- 로컬 전체 테스트는 745건 통과(선택형 LangExtract 실제 파서 검사 1건은 서비스 기본 venv에 패키지가 없어 skip), 별도 실험 venv의 실제 파서 테스트 15건 통과, `git diff --check` 통과. Linux CI와 독립 리뷰는 push 후 확인한다.

## 독립 리뷰 이후

- 첫 push `8dec3b4`의 Linux CI `36579794117`은 성공했다. 독립 리뷰는 중복 anchor가 정렬 충돌 때문에 자동 확정되는 경로와, 서로 다른 anchor가 라이브러리의 중복 부분 위치 때문에 과잉 보류되는 경로를 재현했다.
- 원문에서 검증된 위치를 기준으로 정렬 충돌 행까지 중복 검사하고, 평가기의 중복 판정은 신뢰하지 않는 라이브러리 위치 대신 검증 결과를 사용하도록 수정했다. 두 결함의 회귀 테스트는 수정 전 실패하고 수정 후 통과했다.
- 수정 후 로컬 전체 748건 통과(선택형 실제 파서 1건 skip), 실험 venv 실제 파서 17건 통과, `git diff --check` 통과. 고정 합성 18건을 다시 실행한 결과 완료 18/18, 실패 0, 자동 오확정 0, 허용 누락 0, 중복 위치 0, 제공자 호출 15회였다. 안전 결과는 `E:/AgentFit/tmp/langextract-anchor-adversarial-20260929-reviewfix.json`에 보관한다. 최종 커밋의 Linux CI는 push 후 별도로 확인한다.
