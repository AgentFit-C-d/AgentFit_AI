# 검증 기록: DeepSeek 추론량25

## 로컬 검증

- LangExtract1.7.0을 analysis-runtime/.venv에서 확인. 공유 설치 경로는 미확인, 공유 환경 수정 없음.
- focused: 신규3 테스트 RED(지원하지 않는 thinking_effort)→GREEN, 기존 포함13/13(0.018s).
- 전체1009건:1004통과/5선택 의존성 제외(20.258s). 실제SDK4/4(0.044s). 제품ab60f8e.
- preflight: 합성20(확정7)·audit20·최대4호출, H02183·audit16·부분6·최대14호출. API0. frozen dict 길이를 세던 로컬 점검 오류를 candidates 길이로 수정 후 통과.

## 실행 고정 조건

- structured_output=False, 상세 schema는 system prompt에 보존. off 대 on+reasoning_effort25. 모델 내부의 실제 effort 적용 정도는 미확인.
- temperature0, max8192, timeout600, batch20, reasoned_review, explicit-v1, 재시도0.
- 드라이버 E:/AgentFit/tmp/run-deepseek-effort-h02-v1.py SHA256 ef77add05164ba1803efb5f8eabcb1ba24e9174f5a5e5d05a4c2e0bad0bc6b79.
- helper run-deepseek-thinking-h02-v1.py SHA256 4c3b8a0e6dc382b1cbecff0268de5e1f71e81b6b04faf1ee4e85308ff4a4917a.
- H02 snapshot SHA256 b3072792ee68f6ec02655bcb152f44606047cd094744d4117430414019c3256e. 16개 후보 판단/6개 부분 정답은 이전 고정 정답이며 독립 held-out이 아니다.
- request_bytes는 parser 변환 전 값이며 실제 wire 크기로 해석하지 않는다.

## 결과

합성 session95129 terminal/exit0,4calls136.833s. off/on25 각각 audit20/20,부분1/1,후보/coverage 계약2개 모두 유효. off55.765s/on81.051s. on completion tokens924/437,reasoning chars1974/1211(텍스트 저장 없음). 둘 다 필수 값이 비어 needs_confirmation이며 전체 Profile 완료로 해석하지 않는다. terminal·코드/실행기/helper 불변·순서·effort·schema·상한·재시도 없음·실패 미채점·완주 후 채점 감사11항목 통과, gate=true.

H02는 이 gate로 실행 예정. 품질 개선 여부는 아직 미확인.

## 제한

한 문서의 튜닝 비교이고 전체 Profile 정답이 아니다. 최종 실제 서비스 채택과 준비도, Spring 연동, 독립 문서 일반화는 별도 검증이 필요하다. 원문·인용·키·원시 응답·추론 텍스트는 보고서에 저장하지 않는다.
