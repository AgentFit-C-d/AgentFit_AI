# 원문 기반 독립 역할·상태 판정
사용자 승인: 정확 인용 후보를 고정해 Jev가 역할/상태를 독립 분류하고 통과 시 추출과 연결.
## 범위
state에는 원문·정확 인용·구분 문맥만 전달한다. 추출 모델의 field/role/status/scope 및 정답은 전송하지 않는다.
인용은 먼저 서버에서 정확 위치와 유일성을 검증한다. 역할과 상태는 같은 API 요청의 별도 choice 질문이다.
role: product_function / operating_technology / development / example / unknown.
status: confirmed / tentative / withdrawn / absent / unknown.
역할은 용도, 상태는 그 용도에 대한 확정성이다. 운영 후보도 tentative일 수 있고 개발 도구도 confirmed일 수 있다. 역할을 현재 운영채택 여부와 혼동하지 않는다.
## 평가
12개 사전 고정 합성 문서/인용 × 선택지 정순·역순 =24호출. 후보별 역할정답·상태정답·동시정답,12쌍일관성,잘못된제품확정 판정을 집계.
통과 기준: 동시정답22/24 이상,12/12쌍 역할/상태 일관, 잘못된 product_function 또는 operating_technology + confirmed 판정0.
확률/confidence는 기록만 하며 사후 임계값을 고르지 않는다.
사례에 맞춘 프롬프트 재수정 없이1회 평가. 미통과면 추출 통합을 보류하며 기존분석기는 유지.
## 한계
기존 실험에서 노출된 실패 유형에 기반한 합성 사례다. 독립적인 실제 문서 holdout은 아니다.
전체Profile/인용추출/외부연동 통합/기존호출예산을 검증하는 실험이 아니다.
