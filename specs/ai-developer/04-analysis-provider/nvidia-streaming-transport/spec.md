# NVIDIA 긴 요청의 전송 보완

## 목표와 근거

실사용 가능한 전체 문서 분석이 목표다. 직전 통합 실행은 Solar 추출 2회 뒤 DeepSeek 동작 추출에서 302,234ms 만에 `PROVIDER_UNAVAILABLE`로 끝났다. 요청 제한은 600초였으므로 로컬 600초 제한에 도달한 것은 아니다. 실제 5xx 번호·상류 원인·스트리밍의 해결 효과는 아직 모른다.

공식 [문제 해결 문서](https://docs.nvidia.com/nim/large-language-models/latest/troubleshooting/requests.html)는 같은 모델의 짧은 요청 비교와 프록시 제한 점검을 권한다. [NIM 시작 문서](https://docs.nvidia.com/nim/large-language-models/latest/tutorials.html)는 SSE 스트리밍 및 `[DONE]` 종료를 설명한다. [해당 모델 예제](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash)는 일반 응답 모드이므로, 이 모델의 현재 실제 스트리밍 호환성은 직접 확인한다.

## 접근과 첫 검증

1. 시간 제한만 늘리기: 이미 600초 전에 제공자 오류가 발생했다. 먼저 적용할 근거가 부족하다.
2. 문서 분할: 출력량을 줄일 수 있으나 전역 문맥과 후보 범위가 바뀌므로 별도 품질 검증이 필요하다.
3. **우선 검증:** 같은 짧은 창작 문서·모델·스키마·출력 상한으로 일반 응답과 스트리밍을 한 번씩 비교한다. 기본 전송·의미 판단 정책은 아직 바꾸지 않는다.

합성 문서: `TinyArchive uses PostgreSQL. Users create notes and search notes.`
기존 동작 추출 payload를 재사용하고 `max_tokens=512`, DeepSeek thinking=false를 유지한다. 차이는 stream bool과 Accept 헤더뿐이다. 각 요청 최대 600초, 응답 최대 16MiB, 부모 subprocess가 전체 기한을 강제한다. 자동 retry/fallback은 없다. 최대 2회 전송.

기록: 실제 HTTP 상태, 허용된 콘텐츠 유형, 첫 데이터·첫 content 시간, 전체 시간, 바이트·이벤트·출력 글자 수, 종료 이유의 허용 enum, 요청 모델 일치 여부, 파싱·원문 인용 검증·두 동작 포함 여부. 원문·생성 내용·키·헤더/오류 본문은 출력하거나 저장하지 않는다. 키는 부모 메모리에서 stdin으로 자식에게만 전달하고 argv/env 파일로 넘기지 않는다.

## 판정과 후속 범위

- 둘 다 짧은 요청 성공: 긴 요청의 출력량/대기/중간 프록시 가설을 구분하는 다음 실험을 설계한다. 짧은 성공만으로 H02 문제가 해결됐다고 하지 않는다.
- 일반 응답 실패·스트리밍 성공: 출력 계약을 보존하는 bounded SSE 어댑터의 구현 근거로 사용한다.
- 스트리밍 실패: 오류 유형을 기록하고 같은 모드를 무작정 반복하지 않는다. 문서 분할 등 다음 가설을 검토한다.
- 두 모드 모두 인증/서비스 실패: 해당 외부 상태와 문서 품질을 분리하고, 네트워크가 필요 없는 구현·검증 작업을 계속한다.

본 문서는 첫 진단 범위다. 유지할 제품 코드는 결과에 맞춰 정확한 SSE 계약·예산·취소/종료·테스트를 추가한 명세와 계획을 작성한 뒤 구현한다. 사용자 자율 설계·계획·구현 승인에 따라 별도 승인 질문은 하지 않는다. 개인 문서 발췌 열람 승인 대기는 유지한다.

## 진단 결과와 선택

2026-09-30 probe 두 모드 모두 HTTP200/stop/원문검증/두동작포함 성공. 일반17,468ms,stream20,841ms(첫content16,830ms). 이는 짧은 요청과 스트리밍 호환성을 증명한다. 긴 요청의 5xx 원인이나 속도 개선을 증명하지 않는다. 실측의 입력·스키마·모델·출력예산을 유지하고 전송만 바꾸는 bounded SSE 어댑터를 구현한다.

## 유지할 제품 계약

`nvidia_streaming.post_nvidia_streaming(payload, api_key, timeout) -> bytes`는 기존 transport와 같은 계약이다. 복사한 payload의 stream만True로 바꾸며 자동retry/fallback/토큰축소는 없다. 기존 NVIDIA3모델만허용,timeout은유한실수0초초과600초이하,bool금지. 키는비공백문자열,입력JSON은기존10MiB이하. 키·원문은argv/env/stdout로그에없다.

부모가 기존Solar패턴처럼 별도 `nvidia_stream_worker`를 `subprocess.run(timeout=timeout)`으로 실행한다. 자식stdout은 S+정규화응답 또는 E+허용오류코드만,stderr는폐기한다. 기존env허용목록을재사용한다. 부모의고정NVIDIAendpoint를기존Solar처럼IPC로전달하며호출자가함수인자로endpoint를바꿀수없다. 자식은이서버제어endpoint를호출하고redirect거절·identity인코딩·SSEContent-Type을검증한다. 부모기한은연결/DNS/느린chunk/조립전체에적용한다. 이구조로기존테스트관례대로부모endpoint상수만로컬서버로patch해실제자식시간제한·SSE수신을검증할수있다.

순수 `_assemble_sse(chunks, expected_model) -> bytes`:
- 임의bytes조각에서LF/CRLF줄과빈줄event를조립한다. data여러줄은newline으로합치고주석/미지원SSE메타필드는무시한다. UTF8/JSON이잘못되면실패한다.
- wire전체최대16MiB,event/미완성줄최대1MiB,완성응답최대기존1MiB. reasoning_content/reasoning은형식만확인하고최종content에합치지않는다.
- 모델은적어도한event에서요청모델과정확히일치해야하고명시된모든model은같아야한다. choice는index0인단일선택,role은assistant만허용한다. 명시된completion id는일관되어야한다.
- content문자열을순서대로합친다. tool/function/refusal출력은일반텍스트성공으로바꾸지않는다. usage메타event는허용하며없는usage를0으로조작하지않는다.
- 유효한finish_reason과`[DONE]`둘다필수. finish뒤content·이중finish·잘못된choice는실패한다. EOF/잘린stream은INCOMPLETE_RESPONSE. length등비stop종료는그대로완료envelope에보존해기존Solar/Nvidia분석기가INCOMPLETE_RESPONSE로거절한다. stop이라도JSON/스키마검증은기존분석기가수행한다.
- 반환은기존chatcompletion envelope bytes다. 부분문자열·추론텍스트를Profile로반환하거나저장하지않는다.

HTTP오류는기존safe코드로분류한다. 모델불일치PROVIDER_MODEL,프로토콜형식오류INVALID_RESPONSE,미완료INCOMPLETE_RESPONSE,크기초과RESPONSE_TOO_LARGE. 부모는허용코드외자식출력을PROVIDER_NETWORK로처리한다.

## 연결과 실문서 검증

선택형통합함수의기본NVIDIAtransport만새어댑터로바꾼다. 명시적으로주입한transport는그대로사용한다. 일반기본HTTP/Solar서비스,원문추출/분류/검토/대표구성정책,호출수64/8192토큰/600초는그대로다. 기존일반NVIDIAtransport는명시비교용으로남긴다.

H02는승인된API평가를새추출부터1회실행한다. 드라이버의NVIDIA전송도새어댑터를명시해기존wrapper가일반모드를우회주입하지않게한다. 현재실패3call기록을보존하고,코드/요청/문서해시와새보고서/동일실행핸들로관찰한다. 실패면정확단계와미평가분모를남긴다. 의미정확도·서비스완료는이전과같이별도관문이다.

## 자체검토

기존transport인터페이스와공통호출계측을유지한다. 부분stream을성공으로바꾸지않고완성종료·모델·JSON검증을모두거친다. subprocess로총기한을보장한다. 새네트워크retry나개인정보출력을추가하지않는다. 사용자자율승인에따라직접구현한다.
