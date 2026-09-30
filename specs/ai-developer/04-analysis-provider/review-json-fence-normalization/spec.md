# 검토 JSON 코드 블록 정규화

## 근거와 목적

직전 H02첫20개 형식비교에서 동일prompt의guided응답은통과,prompt-only응답은완전한JSON코드블록과일치하는필수키를갖췄지만CONTENT_JSON으로거부됐다. 이번에는 결정적인외부포장정규화를추가해전체검토와의미채점을재개한다. 단순구문통과를실사용완료로판정하지않는다.

## 계약

- normalize_review_json_fence(raw, expected_keys)→(bytes, normalized_bool). 이미정상인JSON응답은원본bytes를그대로반환한다.
- 기존diagnostic이CONTENT_JSON이면서fenced_json/fenced_object_keys_match=True인경우에만완전한단일fence의본문을message.content로대체한다. json/no-language/대소문자JSON,LF/CRLF,바깥공백허용은기존고정진단규칙과같다.
- envelope/선택지/message형태,stop종료,refusal/toolcalls없음,엄격중복키검사,내부object/정확한최상위필수키집합을먼저확인한다. partial JSON,앞뒤설명,여러블록,다른언어,불완전응답,중복키,없는/추가키는정규화하지않는다.
- model·usage·reasoning·기타envelope값은보존하고content만바꾼다. 키/ID/값/사유를추가·삭제·변경하지않는다. 실제채택은이후기존파서·민감정보·모델·ID/사유·근거·의미검증이판정한다.
- 입력/출력1MiB한도. 재인코딩실패/상한초과면원본과False를돌려기존실패경로를유지한다. expected_keys는기존진단과같이검증한다.
- evaluate_thinking_reviews에normalize_json_fences=False를추가한다. exact bool만허용. True에서만전송후정규화하고시도에json_fence_normalized Boolean을기록한다. capture_response_shape는항상변환전관측이다. 기본서비스와공개Profile은유지한다.

## 실제검증

approved redacted H02,frozen183후보(confirmed109),기존16후보판단/6부분정답을사용한다. DeepSeek thinkingFalse/temp0/8192/600s/20batch/reasoned_review/explicit-v1/schema prompt/streaming/재시도0. 정규화후원래파서를거쳐6후보묶음+전체coverage,최대7호출을1회실행한다.

첫요청이직전형식비교prompt-only요청hash와같음을preflight로확인한다. 과거실패를반복하기위한별도control호출은없다. 전체검토성공시에만투영·16/6채점한다. 실패는미평가다. 정규화빈도·단계·고정코드·ID·개수·hash만기록한다. 원문/응답/추론/private값저장없음. 기존결과덮어쓰기없음.

## 완료기준·한계

동일byte유지·완전fence·불완전/복수/잘못된키·length/refusal/toolcalls·모델/민감정보/ID검증유지·메타데이터보존·한도회귀,전체/SDK검증,최대7회실험terminal감사,독립리뷰와featurepush. H02는튜닝자료,단일실행은일반화/반복안정성증거가아니다. 전체실사용목표의독립품질·서비스연결·Spring등은별도다.
