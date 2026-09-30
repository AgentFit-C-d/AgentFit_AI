# 대표 문구와 문맥의 범위 진단

## 근거와 가설

58c8e52의 고정분할 평가v1은 종료됐고 명확한36판정 중29개 일치,보류0이다. 원래6관계는6/6,역순30관계는23/30이다. 역순의C009를 대표로 둔C013/C056/C067/C069/C111/C131/C160은 사전 기준상 미포함인데 covered로 응답했다. 대표 자신9개를 미포함으로 지목하는 모순은 서버 계산으로0이 됐지만,7개의 오포함이 있어 단순 총점 상승을 채택 근거로 삼지 않는다.

원문 대조에서 C009는 제출 조건절이고 인접 after에 추출 동작 절이 있다. 모델이 주변 절의 능력을 대표 문구에 더해 해석했을 가능성이 있다. 모델 추론은 저장하지 않았으므로 원인으로 확정하지 않는다.

## 한정 실험

제품 코드는 동결하고 기존 두 분할·38관계·사전36판정/2모호·모델/온도/출력/timeout을 유지한다. 검토 system message에만 다음 일반 규칙을 추가한다.

> The selected representative.value is the text used as the displayed feature, not the whole surrounding paragraph. Context may resolve references, scope or an established alias identity; it must not add a separate action or capability that is absent from that selected value. In particular, a conditional/action fragment does not inherit the actions of the following clause. Evaluate whether the selected value represents the member capability, rather than whether both belong to the same workflow. Preserve genuinely equivalent names and descriptions; do not reject aliases merely because their wording differs.

이는 특정 제품명·후보ID·정답을 프롬프트에 추가하지 않는다. 입력 제출이 후속 처리 전체를 대표하지 못한다는 기존 규칙의 해석 범위를 구체화한다. 원래6개의 별칭/반복 관계도 함께 실행하여 지나친 문맥 배제로 유효 관계를 거절하는지 확인한다.

새로 `candidate-feature-relations-h02-20260930-v2.json`에 최대2호출,재시도0,후보생성0을 기록한다. 동일 모델이라도 재실행 변동이 있으므로 한 번의 점수 차이로 인과/재현성을 입증하지 않는다. 원문·키·응답 전문은 저장하지 않는다. 제품 프롬프트는 이 실험 중 변경하지 않는다. 결과에 따라 다음 수정 여부를 결정하며 서비스 목표는 유지한다.

## 종료 결과와 반영 결정

셸92390/PID26072 exit0,finished/code_unchanged=true。총33,153ms,호출7,308ms/25,835ms다. 원래6/6,역순28/30,전체34/36이며 보류0이다. 이전7개 오포함은모두not_covered로바뀌었다. 대신C134/C110의유효관계2개를not_covered로판정했다. 모호C081/C129는두실험모두covered지만정답집계에서계속제외한다. 출력은계속needs_confirmation이고다른9필드/labels는변하지않았다.

v2의request_bytes는transport에서system을추가하기전기존파서가측정한값이므로실제변경후wirebytes로해석하지않는다. added_instruction_sha256와prompt_variant로변경을기록했다.

오포함을낮추면서원래별칭6건을유지한일반규칙을제품helper에반영한다. 이는단일튜닝문서의신호이며정확도94.4%를전체서비스에적용하지않는다. 문구검사단위테스트대신두고정분할에서기존코드+실험추가문구와새제품요청이메모리상완전히같은지검증한다. 더넓은문서/합성사례/반복과유효관계2건의보완은다음품질관문이다.

## 반영 후 확인

메모리 요청 비교에서 원래 6쌍·역순 32쌍 모두 v2 실험 요청과 새 제품 요청이 정확히 일치했다. 외부 호출과 요청 파일 저장은 각각 0회다. 임시 원본의 CRLF를 LF로 정규화하면 실제 평가 코드 해시와 일치했다. 제품 수정 후 전체 테스트는 907개 중 901개 통과, 6개 건너뜀, 실패 0개였다. 전체 결과와 제한은 validation.md에 기록한다.
