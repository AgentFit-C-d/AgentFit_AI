"""Current-server reproduction before editing; offline, no successful review invented."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'ai_service'),str(ROOT/'ai_service/tests')]
from review_preservation_fixture import offline
from tentative_proposed_fixture import case,unreviewed_boundary
from agentfit_ai.candidate_semantic_assessment import validate_assessments

OUT=Path('E:/AgentFit/output/tentative-proposed-preservation-20261003-v1')
with offline():
    OUT.mkdir(parents=True,exist_ok=False)
    rows=[]
    for doc in ('D1','D2'):
        for arm in ('A','B'):
            document,frozen,raw,old=case(doc,arm)
            records=validate_assessments(document,frozen,raw,require_mention_kind=True)
            assert records==old
            for row in records:
                if doc=='D2' and row['id']=='C006':
                    assert row['decision']=='excluded'
                    rows.append({'document':doc,'arm':arm,'record':row,
                        'sourceValue':document[row['candidate']['start']:row['candidate']['end']],
                        'firstCause':'_decision final exclusion: commitment != adopted',
                        'exclusionTerms':{'scope_not_target':row['scope']!='target','time_not_current':row['time']!='current',
                        'polarity_not_positive':row['polarity']!='positive','commitment_not_adopted':row['commitment']!='adopted',
                        'role_not_product_fact':row['role']!='product_fact','field_other':row['field']=='other',
                        'negated_or_irrelevant':row['modelStatus'] in ('negated','irrelevant')}})
                    for contract in ('confirmation-v2','confirmation-v3'):
                        packet=unreviewed_boundary(document,[row],contract)
                        with (OUT/f'before-{arm}-{contract}-boundary.json').open('x',encoding='utf-8') as f:
                            json.dump(packet,f,ensure_ascii=False,indent=2)
    evidence={'matchedStoredRows':32,'affected':rows,'modelCalls':0,'externalNetwork':0,
              'boundaryKind':'synthetic unreviewed envelope; no real subsequent review available',
              'serviceSha256':hashlib.sha256((ROOT/'ai_service/agentfit_ai/candidate_semantic_assessment.py').read_bytes()).hexdigest()}
    with (OUT/'before.json').open('x',encoding='utf-8') as f: json.dump(evidence,f,ensure_ascii=False,indent=2)
    print(json.dumps(evidence,ensure_ascii=False,indent=2))
