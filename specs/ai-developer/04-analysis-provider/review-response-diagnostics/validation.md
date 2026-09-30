# 검토 응답 형식 진단 검증

## 구현·로컬 테스트

- 제품7802b5c. 독립 진단함수는 고정 enum/count/Boolean/null만 반환한다. capture_response_shape=False가 기본이며 True에서만 시도별 형태를 추가한다. 기존 서버 파서·의미 검증·기본 서비스 그대로다.
- 신규 진단10/10,선택형 평가16/16. 구현 전 모듈/선택 인자 부재의 RED를 확인했다.
- 깊이2000의JSON배열은 현재Python에서 유효하게 읽혀 root 형태로 거부됐다. 이 경우와 실제 parser RecursionError를 구분해 테스트했다.
- 최초전체1022건/1017통과5선택의존성skip(20.046s),실제SDK4/4(0.045s). fence테스트를강화해민감정보오류에가려지지않고INVALID_RESPONSE로실패함을16/16으로재확인했다. 최종task-done도1022건/1017통과5skip(20.088s),실제SDK4/4(0.049s),exit0이다.

## 고정 실제 실험

- E:/AgentFit/tmp/run-review-format-h02-v1.py SHA256 b383d0997d3ade22447153feaf193dbc217d60fe263b1b34235f3d62e1d6a884.
- 기존helper SHA256 4c3b8a0e6dc382b1cbecff0268de5e1f71e81b6b04faf1ee4e85308ff4a4917a, H02snapshot b3072792ee68f6ec02655bcb152f44606047cd094744d4117430414019c3256e.
- 첫confirmed20개,동일문서/후보/순서/기본prompt/전체schema prompt,thinkingFalse/temp0/8192/timeout600/streaming/재시도0. response_format 유무만 다름.
- session59124/PID37548 terminal/exit0,2calls90.946s. 코드·driver·helper·source·snapshot·request불변,차이통제,상한,순서,의미미채점,재시도없음 등 감사12항목 통과. 실행기exit0은 실험완료이며 두조건 모두분석성공이라는 뜻이 아니다.

| 조건 | 첫 묶음 계약 | 관측 |
|---|---|---|
| guided schema + schema prompt | 통과 | JSONobject,필수키누락/추가0,stop295tokens,45.072s |
| schema prompt만 | 실패/INVALID_RESPONSE | CONTENT_JSON,fenced_json=true,fenced_object_keys_match=true,stop299tokens,45.859s |

## 판단과 남은 문제

이번 prompt-only 응답은 완전한Markdown JSON fence로 감싸져 있었다. 내부JSON이object이고필수키집합이맞는다는Boolean을 확인했다. 본문/키이름/값/추론/예외내용은 기록하지 않았다. 이 재현에서는 형식 포장이 파서 거부의 원인이다. 이전 raw가 없는 모든실패의원인이같다고단정하지않는다.

fence 안의 ID·사유·의미를 별도로 채점한 것은 아니다. 한 묶음이며 전체H02/Profile 정확도·일반화·운영채택은 미확인이다. on25의length 실패도 별도다.

다음 보완은 완전히 감싼 단일JSON fence만 결정적으로 제거한 뒤 기존키/ID/근거/의미검증을 그대로 적용하는 선택형 경계 정규화다. 부분JSON복구·임의텍스트추출·내용수정은 허용하지 않는 설계가 필요하다. 이번feature의진단은응답을수정하지않는다. 후속 구현 후 전체H02로 의미평가를 재개하고,추론을켜야할때만묶음/출력예산문제를별도로검증한다.

## 감사 산출물

- safe결과: E:/AgentFit/tmp/review-format-h02-20260930-v1.json
- 감사기: E:/AgentFit/tmp/audit-review-format-h02-v1.py
- SDD기록: .superpowers/sdd/plan-review-response-diagnostics/
- 실제API프로세스없음,총2호출,기존결과보존.

## 최종 리뷰·브랜치

독립리뷰0Critical/0Important/0Minor. reviewer직접26/26과callback8개비공개표식미노출을확인했다. 원문재대조/전체의미품질은판단하지않았으며 [부모 판단과 제한](../../../../work/harness/review-response-diagnostics/review.md)에기록했다. 실제진단코드를포함한258bad9의 [CI36692717666](https://github.com/AgentFit-C-d/AgentFit_AI/actions/runs/36692717666)은두job모두통과했다. feature/review-response-diagnostics에push했으며최종문서push/CI는도구결과와ignored SDDledger에기록한다. 실제서비스배포나기본설정변경은없다.
