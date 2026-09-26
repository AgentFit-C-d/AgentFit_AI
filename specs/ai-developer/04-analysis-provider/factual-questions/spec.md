# 마지막 튜닝: 네 가지 사실 확인
승인: 새 합성 기준을 고정하고 기존 방식과 비교. 통과 시 실제 문서, 미달 시 추가 튜닝 없이 종료.
## 질문
current: 후보 설명이 현재 대상 제품에 관한가?
adopted: 대상 제품의 실제 운영/기능에 사용·제공한다고 명시했는가?
rejected: 대상 제품에서 사용하지 않거나 철회한다고 명시했는가?
development_only: 개발/테스트/시연 전용이라고 명시했는가?
각 질문은 yes/no/unknown. yes는 명시적 근거, no는 반대의 명시적 근거, 미언급·모호함은unknown.
## 서버 결정
adopted와rejected가모두yes, 또는개발전용과제품운영채택이모두yes, 또는다른제품인데채택yes이면 unknown.
current=no 또는rejected=yes 또는development_only=yes이면exclude.
current=yes,adopted=yes,rejected=no,development_only=no 모두충족하면adopt.
그외unknown. unknown을임의채택하지않는다.
## 비교
새 합성12사례 × 선택지2순서 × 기존2축/신규4질문 =48호출.
모델Jev와원문·인용을동일하게하고 기존역할상태판정은프롬프트수정없이실행. 실행순서는사례별교차한다.
공통평가단위는adopt/exclude/unknown. 기존2축은제품기능/운영기술+confirmed를adopt, 개발/예시또는absent/withdrawn을exclude,그외unknown으로매핑.
신규개별질문정답도별도집계. 12문서는개발중작성합성사례로실제문서holdout은아니다.
## 사전 게이트
신규최종결정22/24이상,4질문정답88/96이상,정순역순최종결정12/12일관,잘못된adopt0.
기존방식보다최종정답이높아야실제문서평가로확대. 이기준하나라도미달하면프롬프트추가튜닝없이이번실험종료.
전체분석기/API/서비스UI는변경하지않는다.
