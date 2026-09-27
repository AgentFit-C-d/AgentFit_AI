"""Server-built occurrence views over unchanged source text."""
from .anchored_prompts import CANDIDATE_PROMPT_V2, JUDGMENT_PROMPT_V2
from .solar import AnalysisError

CANDIDATE_EXPANSION_PROMPT = CANDIDATE_PROMPT_V2.replace(
    "인용은 해당 unit.text 안에서 정확히 한 번 등장해야 한다. previous/next/제목 문맥에서 가져오지 않는다.",
    "인용은 해당 unit.text 안에 정확히 존재해야 한다. 같은 문자열이 여러 번 나와도 문자열을 quotes에 한 번만 적는다. 서버가 모든 위치를 열거한다. previous/next/제목 문맥에서 가져오지 않는다.")
JUDGMENT_FOCUS_PROMPT = JUDGMENT_PROMPT_V2.replace(
    "같은 값 반복은 duplicate.",
    "같은 이름의 각 위치에서 대상·역할·상태를 먼저 판단한다. duplicate는 적격인 동일 최종 사실의 중복에만 사용한다.") + """
후보의 focus.selected는 해당 ID가 가리키는 특정 위치의 인용이다.
focus.before와 focus.after는 그 위치의 바로 앞뒤 원문이다. beforeTruncated/afterTruncated가 true이면 문맥 일부이며 전체 원문과 headingPath도 확인한다.
같은 quote의 다른 ID는 다른 위치다. 개발 문장의 ID와 운영 문장의 ID를 혼동하지 않는다.
문자 위치나 등장 순서는 계산하지 말고 각 ID의 focus와 전체 원문으로 판단한다.
"""

def candidate_views(pool,sections,*,focus=False):
    mapping={u.id:u for u in sections};result=[]
    for item in pool:
        view={k:v for k,v in item.items() if k!="span"}
        if focus:
            unit=mapping[item["unitId"]]
            start=item["span"]["start"]-unit.start;end=item["span"]["end"]-unit.start
            if not 0<=start<end<=len(unit.text) or unit.text[start:end]!=item["quote"]:
                raise AnalysisError("ANCHORED_CANDIDATE")
            view.update(focus={"before":unit.text[max(0,start-160):start],
                "selected":item["quote"],"after":unit.text[end:end+160]},
                headingPath=list(unit.path),beforeTruncated=start>160,afterTruncated=end+160<len(unit.text))
        result.append(view)
    return result
