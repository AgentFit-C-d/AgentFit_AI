# 검토 응답의 안전한 형식 진단

## 문제·목표

이전 H02에서 off는 finish=stop에도 INVALID_RESPONSE로 실패했고, on25는 네번째 묶음에서length8192로 실패했다. raw를 저장하지 않아 off가 JSON문법/둘러쌈/루트형태/필수키 중 어디서 틀렸는지 모른다. 형식 진단을 통해 수정 대상을 특정하고, 이후 묶음 크기 보완과 의미 평가를 재개할 근거를 만든다. 전체 실사용 목표는 유지한다.

## 설계

- 별도 순수함수 describe_review_response(raw, expected_keys)를 추가한다. 입력은 응답bytes와 이미 알려진 필수키목록이다. bytes상한1MiB·기대키1~32·유일문자열을 검증한다.
- 출력은 고정 issue enum, 고정 content type enum, 길이/개수, Boolean/null만 허용한다. 실제 키 이름·값·본문·추론·예외 메시지·원본응답은 반환하지 않는다.
- envelope JSON·선택지·message·finish·content JSON·루트type·필수키일치를 구분한다. 완전히 감싼 단일 Markdown JSON fence의 내부가 JSON인지도 Boolean으로만 진단한다. fence를 벗겨서 정상응답으로 채택하지 않는다.
- 기존 엄격 _json 파서를 재사용하고 깊이초과는 고정 진단으로 제한한다. 진단은 구조 관측이며 민감정보/ID/의미/근거에 대한 전체 유효성 판정이 아니다.
- evaluate_thinking_reviews에 capture_response_shape=False를 추가한다. exact bool을 호출 전에 확인하며 True에서만 transport_attempts에 response_shape를 붙인다. 기본전송·서버검증·공개Profile·기본서비스는 그대로다. 잘못된 JSON을 성공으로 바꾸거나 재시도하지 않는다.

## 한정 실제 실험

승인된 개인정보 제거 H02와 고정183후보의 첫 confirmed20개를 사용한다. 전체 문서·후보·temp0·8192·timeout600·thinkingFalse·reasoned_review·explicit-v1·streaming을 고정한다. 양쪽 system prompt에 동일한 전체 schema를 넣고 한쪽에만 response_format=json_schema를 추가한다. 즉 guided decoding 유무만 다른 두 요청을 각1회,최대2호출 실행한다. 기존snapshot/source/helper/코드hash를 검증하고 gold를 보내거나 수정하지 않는다.

유효한 응답은 기존 _send_payload 및 후보ID·거부사유 계약까지 확인한다. 첫 묶음의 계약 통과율과 형태 진단만 보고하고 전체 H02나 의미 정확도를 채점하지 않는다. 실패/제공자거부도 terminal로 남긴다. 기존 결과덮어쓰기/무한재시도/추가private발췌는 없다. 실제 형식오류가 재현되지 않으면 원인은 미확인으로 남긴다.

## 완료 기준

진단 분류·privacy·경계·기본호환·서버실패유지 테스트,전체/SDK검증,최대2실제호출의 terminal 감사,SDD기록,독립전체브랜치리뷰와featurepush. 실제품질개선/운영채택/전체목표완료와 구분한다.
