"""Opt-in expression-boundary prompt and frozen evaluation-only cases."""
import json
from pathlib import Path
from .profile import FIELDS, validate_profile
from .semantic_review import REVIEW_PROMPT

def expression_prompt():
    old = "  문장 주어·조사·서술어를 포함한 과도한 범위, 여러 동작을 한 문장으로 묶으면 overbroad다."
    new = """  하나의 동작을 나타내는 문장에서는 행위자 주어·목적어·조사·서술어를 허용한다. 문장이라는 이유만으로 overbroad가 아니다.
  '필수 기능:', '주요 기능은' 같은 목록/범주 접두사와 제목은 값에서 제외한다. 여러 독립 동작을 한 항목에 묶으면 overbroad다."""
    assert old in REVIEW_PROMPT
    return REVIEW_PROMPT.replace(old,new) + """
ai와 external_integrations의 값은 채택된 구체적 모델/제공자 이름이다. 이름 앞뒤의 채택 설명 문장까지 값으로 포함했으면 overbroad다.
배열의 기존 항목 문제(overbroad/duplicate/uncertainty 등)는 반드시 그 항목의 0부터 시작하는 정수 itemIndex를 쓴다.
배열 전체에 걸친 문제도 문제 항목마다 별도 이슈를 만든다. missing/스칼라/명시적 빈 배열의 오류만 itemIndex=null이다.
"""

def cases():
    source=Path(__file__).resolve().parents[2]/"specs/ai-developer/04-analysis-provider/review-expression-rubric/cases.json"
    result=[]
    for case in json.loads(source.read_text(encoding="utf-8")):
        document=case["document"];field=case["field"]
        for state in ("correct","wrong"):
            value=case[state];data=dict.fromkeys(FIELDS);data[field]=value
            evidence={f:[] for f in FIELDS}
            quotes=[] if value is None else value or [document]
            for quote in quotes:
                assert document.count(quote)==1
                start=document.index(quote)
                evidence[field].append({"start":start,"end":start+len(quote)})
            profile=validate_profile(document,case["id"],{"data":data,"evidence":evidence})
            expected=[] if state=="correct" else [{"field":field,"kind":case["kind"],"itemIndex":case["index"],"evidenceLineIds":[1]}]
            result.append({"id":case["id"]+"-"+state,"document":document,"profile":profile,"expected":expected})
    return result
