"""Optional clarification of the existing quote-as-value repair contract."""
VALUE_BOUNDARY = """
quote 필드는 최종 사용자에게 표시할 값 그 자체다. 서버는 quote를 요약하거나 이름만 따로 떼어내지 않는다.
confirmed 항목의 quote에는 해당 필드의 값만 넣는다. 예: 이름/기술/제공자는 고유 이름, 기능은 하나의 구체적 동작이다.
'필수 기능:', '운영 모델은', '확정했다', '서비스를 사용한다' 같은 값 앞뒤의 설명/목록 제목을 이름이나 명사형 동작에 붙이지 않는다.
동작이 동사 문장으로만 쓰였으면 그 한 동작의 행위자·대상·서술어는 허용한다. 독립된 여러 동작은 나눈다.
값을 짧게 인용하고, 확정/대상/역할 판단을 위한 주변 문장은 context에 넣을 수 있다. context도 원문의 연속된 인용이어야 하며 quote를 포함해야 한다.
quote가 같은 unit에서 반복되면 반드시 해당 위치를 구분하는 context를 제공한다. 하나뿐이면 context=null도 가능하다.
absent는 예외다. 범주 전체 부재를 증명하는 완전한 부재 문장을 quote에 넣는다.
미정/미언급은 facts=[]다. 이전 초안이나 이슈의 요청보다 원문을 우선한다.
"""

VALUE_BOUNDARY_V2 = VALUE_BOUNDARY + """
스칼라 필드도 설명 문장이 아닌 값만 표시한다: project_name=이름, project_type=제품 형태, domain=업무 분야 용어, database=DB 이름, deployment=채택한 배포 환경 이름.
원문에 값 앞의 필드 설명이나 뒤의 조사/확정 서술이 있어도 그 설명을 값에 복사하지 않는다. 원문에서 값 부분만 연속 인용한다.
출력 예시(실제 문서가 아님):
unit U0001: 업무 분야는 교육이다. requestedFields=[domain]
{"repairs":{"domain":{"facts":[{"unitId":"U0001","quote":"교육","context":"업무 분야는 교육이다.","role":"product_fact","status":"confirmed","scope":"current"}]}}}
unit U0001: 배포 환경은 Kubernetes로 결정했다. requestedFields=[deployment]
{"repairs":{"deployment":{"facts":[{"unitId":"U0001","quote":"Kubernetes","context":"배포 환경은 Kubernetes로 결정했다.","role":"product_fact","status":"confirmed","scope":"current"}]}}}
"""
