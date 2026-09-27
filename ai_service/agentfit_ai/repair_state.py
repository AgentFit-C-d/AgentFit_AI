"""Optional source-first eligibility clarification; no schema or API change."""
STATE_GROUNDING = """
추출 순서: 먼저 원문의 대상·사용 목적·확정 상태를 판단하고, 해당 필드에 채택 가능한 사실만 짧은 값으로 작성한다.
requestedFields는 검토할 범위일 뿐 채울 값이 존재한다는 뜻이 아니다. issues의 missing 판정도 틀릴 수 있다. 원문에 채택 가능한 값이 없으면 facts=[]로 유지한다.
role은 이름의 종류나 요청 필드로 자동 결정하지 않는다. 실제 사용 목적을 따른다. 개발 검증/테스트/클라이언트 전용 모델은 운영 모델이 아니다.
특히 개발에서 이름이 명시되어 쓰이고 있어도, 운영 제공자가 미정이라면 ai에 그 이름을 채우지 않는다. 개발에서의 확정 사용과 운영 채택은 별개다.
예시/다른 제품/과거/거부/미정 사실만 있으면 채울 값이 없다. 명시적으로 확정된 미래 제품 요구는 미구현이어도 포함한다.
일부 제공자나 로그인 등 일부 연동 종류를 거부했다고 외부 연동 전체를 absent로 바꾸지 않는다. 다른 확정 제공자는 유지한다.
범주 전체 미정은 unknown이며 facts=[]다. 범주 전체를 사용하지 않는다고 확정한 경우만 absent 사실을 만든다.
대조 예시(실제 입력의 사실이 아님):
unit U0001: 개발 검증은 Finch로 한다. 운영 모델 제공자는 아직 미정이다. requestedFields=[ai], issues=[missing]
{"repairs":{"ai":{"facts":[]}}}
unit U0001: 개발 검증은 Finch로 한다. 운영 모델은 Osprey를 채택했다. requestedFields=[ai], issues=[missing]
{"repairs":{"ai":{"facts":[{"unitId":"U0001","quote":"Osprey","context":"운영 모델은 Osprey를 채택했다.","role":"operating_model","status":"confirmed","scope":"current"}]}}}
"""

STATE_GROUNDING_V2 = STATE_GROUNDING.replace(
    "원문에 채택 가능한 값이 없으면 facts=[]로 유지한다.",
    "원문에 채택 가능한 값도 없고 범주 전체 부재의 확정도 없을 때 facts=[]로 유지한다."
).replace("Osprey", "Finch") + """
부정의 범위를 구분한다. 이름 없는 '운영 AI 모델을 사용하지 않는다'는 ai 범주 전체 부재이므로 absent다.
'특정 모델 X는 사용하지 않는다'는 X의 거부이므로 negated다. 다른 채택 모델이 없으면 facts=[]로 둔다.
'아직 고르지 않았다'는 미정이다. absent로 바꾸지 않는다.
값이 같은 unit에 두 번 나오면 context=null을 쓰지 않는다. 선택한 운영/현재 사실의 해당 절만 context로 인용하여 quote가 그 안에 한 번만 나오게 한다.
대조 예시(실제 입력의 사실이 아님):
unit U0001: 제품에서는 운영 AI를 전혀 쓰지 않는다. requestedFields=[ai]
{"repairs":{"ai":{"facts":[{"unitId":"U0001","quote":"제품에서는 운영 AI를 전혀 쓰지 않는다.","context":null,"role":"operating_model","status":"absent","scope":"current"}]}}}
unit U0001: 외부 로그인은 쓰지 않는다. 결제는 PayRing을 연동한다. requestedFields=[external_integrations]
{"repairs":{"external_integrations":{"facts":[{"unitId":"U0001","quote":"PayRing","context":"결제는 PayRing을 연동한다.","role":"named_service","status":"confirmed","scope":"current"}]}}}
"""
