# GLM 부분 결과: 전체 실행 대기

2026-10-01 session91923이 진행 중이다. 공개01·공개07은 완료됐으며, 합성의 완료 결과는 아직 없다. 현재 코드·자료·모델 설정을 변경하지 않는다.

## 완료된 공개01

19호출,1561.002627초(약26분), 응답 계약 유효. 사전등록한 제품 동작4개와 Docker2개를 보존하고 비기능 안내2개를 제외했다. DeepSeek의 같은 검토 입력은19호출/99.928321초,제품 동작0/4·Docker0/2였다. 이 단회·다른시점 비교는 모델과 기존 운용설정의 차이까지 포함하며, 사람 검토 전 임시 기준이다.

## 사후 로컬 Profile 변환

외부0호출로 기존 `finalize_candidate_analysis`에 각 완료 검토를 입력했다. GLM은 features4개, DeepSeek는0개였다. 양쪽 모두 `needs_confirmation`이고 deployment/database는 null이다. GLM은 project_type/domain/backend/database/deployment/features/external_integrations를 확인 필요로 남겼다.

이는 저장된 검토 결과의 결정적 변환 확인이다. 추출·분류·대표 기능 선택을 포함한 전체 실제 분석, 사용자 확인·Spring 저장 검증이 아니다. 상세 안전 메타데이터는 [projection-public01.json](projection-public01.json)에 저장한다.

## 추가 대조와 남은 해석

GLM이 더 보존한23개 후보는 기능4개와 배포 관련 표현19개였다. 반대로 DeepSeek가 유지한 URL 내부 하위 문자열3개(C142/C143/C144)를 GLM은 제외했다. 이 숫자를 전체 의미 정확도나 독립 정답률로 표현하지 않는다. C118처럼 URL 내부에 위치한 표현, 긴/짧은 중복·대소문자 변형은 추가 의미 검토가 필요하다.

deployment는 현재 공개 Profile에서 단일 문자열이다. 지원 배포 방식이 여럿이면 유효 후보를 보존해도 최종 변환에서 자동으로 하나를 선택할 수 없다. [필드 해석 질문](../../../Docs/ai-profile-field-interpretation-review.md)의 답변과 전체 의미·사용자 수정 부담 검증이 남는다. 기존 API 계약·gold·점수를 임의로 바꾸지 않는다.

## 완료된 공개07

14호출/1136.204573초, 응답 계약 유효. 기존 기능14개를 모두 유지했다. 잘못된 후보로 제외한 ID는 external_integrations의 C030/C031/C033/C034이며, 사유는 모두 not_product_fact였다. 누락 필드는 project_type으로 반환했다. DeepSeek의 같은 입력도 기능14개는 유지했다. 이는 기능 보존 회귀 검사를 통과한 것이며 모든 외부 연동·누락 판단의 정확성을 확정하는 결과는 아니다.

## 분류 단계에 남은 누락

API0 사후 대조에서 기존 임시 gold의 U018·U019는 각각 정확한 근거 C059·C061로 추출됐지만 분류 결과가 other/irrelevant였다. 따라서 confirmed만 입력받는 검토 단계에서는 복구할 수 없다. 반면 U020~U023은 features/confirmed였고 GLM이 네 개 모두 유지했다. U017의 포괄적인 비전 표현은 별도 해석이 필요하다. [feature-stage-audit-public01.json](feature-stage-audit-public01.json)은 이 최초 불일치 위치를 저장하며, 사람 검토나 기존 gold 수정은 아니다.

분류는 explicit-v1을 사용하며 기능의 기술 목록 내 용도에 대한 추가 문구는 검토 단계에만 적용된다. 모델 경로와 지침 차이 중 무엇이 원인인지는 아직 확정하지 않았다. 다음 비교에서는 기존 분류 함수의 모델 선택만 바꾸고 원문·후보·기준을 고정한다.

## 로컬 시간 초과 재현

별도 외부0호출 재현에서3초 뒤 marker를 쓰는 자식을1초 timeout으로 실행했다. 부모는1.023초에 timeout,4초 시점 자식 완료 marker없음을 관측했다. 이 한 사례에서 launcher 종료 후 자식 실행 지속 문제는 재현되지 않았다. 실제 서비스 모든 자식 트리의 취소 검증으로 확대 해석하지 않는다. 모델 평가 프로세스에는 신호를 보내지 않았다.
