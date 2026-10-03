"""Separate server-only replay of immutable live responses; no review fabricated."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'ai_service'),str(ROOT/'ai_service/tests')]
from review_preservation_fixture import offline
from tentative_proposed_fixture import case, load, DIRECTORY, unreviewed_boundary
from agentfit_ai.candidate_semantic_assessment import validate_assessments, semantic_labels

OUT=Path('E:/AgentFit/output/tentative-proposed-preservation-20261003-v1')
def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f: json.dump(value,f,ensure_ascii=False,indent=2)

with offline():
    manifest=json.loads((DIRECTORY/'manifest.json').read_bytes())
    for path,expected in manifest['protectedFiles'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected, path
    changed=[]; batches=[]; boundaries=[]
    for doc in ('D1','D2'):
        for arm in ('A','B'):
            document,frozen,raw,old=case(doc,arm)
            original=deepcopy(raw)
            new=validate_assessments(document,frozen,raw,require_mention_kind=True)
            assert raw==original
            delta=[]
            for previous,current in zip(old,new,strict=True):
                assert {k:v for k,v in previous.items() if k!='decision'}=={k:v for k,v in current.items() if k!='decision'}
                if previous!=current:
                    change={'document':doc,'arm':arm,'id':current['id'],'before':previous['decision'],'after':current['decision'],
                            'value':document[current['candidate']['start']:current['candidate']['end']], 'candidate':current['candidate'],
                            'modelStatus':current['modelStatus'],'commitment':current['commitment']}
                    delta.append(change); changed.append(change)
            batches.append({'document':doc,'arm':arm,'before':dict(Counter(r['decision'] for r in old)),
                            'after':dict(Counter(r['decision'] for r in new)),'changed':delta})
            save(f'after-{doc}-{arm}-server.json',{'records':new,'labels':semantic_labels(new),'rawPreserved':True})
            if doc=='D2':
                row=next(r for r in new if r['id']=='C006')
                for contract in ('confirmation-v2','confirmation-v3'):
                    packet=unreviewed_boundary(document,[row],contract)
                    before=json.loads((OUT/f'before-{arm}-{contract}-boundary.json').read_bytes())
                    assert {k:v for k,v in before.items() if k!='modelDecisions'}=={k:v for k,v in packet.items() if k!='modelDecisions'}
                    save(f'after-{arm}-{contract}-boundary.json',packet)
                    boundaries.append({'arm':arm,'contract':contract,'beforeDecision':before['modelDecisions'][0]['decision'],
                        'afterDecision':packet['modelDecisions'][0]['decision'],'modelRecord':packet['modelDecisions'][0],
                        'profileData':packet['profile']['data'],'questionsBefore':len(before['questions']),
                        'questionsAfter':len(packet['questions']), 'envelopeKind':'synthetic unreviewed; all fields unresolved'})
    assert [(r['document'],r['arm'],r['id']) for r in changed]==[('D2','A','C006'),('D2','B','C006')]
    summary={'kind':'server-only offline replay, not a model rerun','matchedRows':32,'changed':changed,'batches':batches,
             'rawResponsesUnchanged':True,'historicalRunUnchanged':True,'protectedFilesUnchanged':True,
             'boundaries':boundaries,'realSubsequentReview':'unavailable','realWholePipeline':'unmeasured',
             'modelCalls':0,'externalNetwork':0,'largeGoalResumed':False,'serviceApplied':False,
             'serviceAfterSha256':hashlib.sha256((ROOT/'ai_service/agentfit_ai/candidate_semantic_assessment.py').read_bytes()).hexdigest()}
    save('after.json',summary)
    print(json.dumps({k:summary[k] for k in ('changed','batches','protectedFilesUnchanged','modelCalls','realWholePipeline')},ensure_ascii=False,indent=2))
