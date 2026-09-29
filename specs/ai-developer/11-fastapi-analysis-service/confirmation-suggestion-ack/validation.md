# 검증 기록 (2026-09-29)

## 재현과 구현

- 의미 검토에서 일부 필드에 이슈가 난 뒤 수정 호출이 실패하면, 이전 복구형 분석기는 나머지 `suggested` 필드의 `confirm_<field>` 질문을 빠뜨렸다. FastAPI 복구 모드도 질문이 없는 `suggested`를 HTTP 200으로 받았다. 두 동작을 실패 테스트로 재현했다.
- 이제 복구형 분석기는 검토 완료 제안에 `CONFIRM_SUGGESTION`, 검토 미완료 제안에 기존 `REVIEW_UNAVAILABLE` 질문을 붙인다. 복구 모드 FastAPI는 모든 `suggested`·`unresolved` 필드의 질문을 요구하고 중복·상태와 맞지 않는 사유를 502로 거절한다. 기본 모드는 기존 동작을 유지한다.
- [내부 인계안](../../../../Docs/api/analysis-confirmation-v1.draft.md)에 질문 집합의 완전성 규칙을 기록했다. 공개 Spring DTO와 확인 PATCH는 여전히 합의 전이다.

## 로컬 실제 경로

합성 `Aurora` 문서를 로컬 FastAPI `TestClient`로 보내 실제 자식 분석 Worker와 Solar를 호출했다. 수정 전 실행은 약 6초 뒤 HTTP 200 `needs_confirmation`, `suggested` 7·`unresolved` 1·질문 8을 반환했다. 수정 후 다른 한 번의 실행은 약 24초 뒤 HTTP 200 `complete`를 반환했다. 같은 문서의 확률적 모델 출력이 달랐으므로 이 둘을 품질 개선량으로 비교할 수 없다. 새 질문 규칙 자체는 가짜 Provider와 ASGI 회귀 테스트로 검증했다. 키·원문·Provider 원본 응답은 검증 기록에 저장하지 않았다.

## 제한

AI 내부 계약의 질문 누락은 막았지만 Spring과 Frontend가 질문 집합·초안 버전·사용자 확인을 원자적으로 저장하고 재조회하는지는 확인되지 않았다. 의미 정확도와 독립 실제 문서 검증도 미달이다. 복구 모드는 운영 기본값으로 활성화하지 않는다.

프로젝트 가상환경의 전체 **583건 테스트**와 staged diff check가 통과했다. 코드 커밋 `5a655f8`을 `feature/confirmation-suggestion-ack`에 push했고 [AI service Linux checks](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36525559918)가 성공했다.
