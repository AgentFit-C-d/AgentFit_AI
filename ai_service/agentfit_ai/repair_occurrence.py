"""Opt-in occurrence addressing over unchanged source units."""
import re
from .evidence import EvidenceError

def resolve_occurrence(text,quote,index):
    if type(quote) is not str or not quote.strip() or len(quote)>2000:
        raise EvidenceError("INVALID_QUOTE")
    if type(index) is not int or not 1<=index<=24000:
        raise EvidenceError("INVALID_OCCURRENCE_INDEX")
    cursor=0
    for _ in range(index):
        start=text.find(quote,cursor)
        if start<0:raise EvidenceError("OCCURRENCE_NOT_FOUND")
        cursor=start+len(quote)
    return {"start":start,"end":cursor}

def occurrence_prompt(prompt):
    # Transform only our frozen prompt examples, never source documents or model output.
    lines=[]
    for line in prompt.splitlines():
        if '"context":' in line:
            line=re.sub(r'"context":(?:null|"(?:[^"\\]|\\.)*")','"occurrenceIndex":1',line)
            line=line.replace('"quote":"Finch","occurrenceIndex":1','"quote":"Finch","occurrenceIndex":2')
        elif "context" in line:
            continue
        lines.append(line)
    return "\n".join(lines)+"""
occurrenceIndex는 해당 unit의 text에서 정확한 quote가 왼쪽부터 몇 번째 등장하는지 나타내는 1부터 시작하는 정수다.
겹치지 않는 정확 일치를 순서대로 센다. unit마다 다시1부터 센다. 하나뿐이어도1을 반환한다.
같은 이름이 개발/예시/과거와 운영/현재에 반복되면, 채택한 운영/현재 사실이 있는 등장 순서를 선택한다.
quote는 짧은 최종 값 그대로다. 앞뒤 설명을 붙이거나 문장을 합성하지 않는다. 일반 값200자/부재 문장2000자, 필드30개/전체120개 이하.
확정 여부와 역할은 원문 전체 문맥으로 판단한다. 순서만 맞다고 운영 확정 사실이 되는 것은 아니다.
"""
