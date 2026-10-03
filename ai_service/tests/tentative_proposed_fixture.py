"""Saved model responses are immutable; projection envelopes are synthetic."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from agentfit_ai.candidate_semantic_assessment import AXES, semantic_labels
from agentfit_ai.candidate_first_profile import project_candidate_profile
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.profile import FIELDS

DIRECTORY=Path(__file__).parent/'fixtures/tentative_proposed'


def load(name):
    manifest=json.loads((DIRECTORY/'manifest.json').read_bytes())
    raw=gzip.decompress((DIRECTORY/(name+'.gz')).read_bytes())
    assert hashlib.sha256(raw).hexdigest()==manifest['files'][name], name
    return json.loads(raw) if name.endswith('.json') else raw.decode('utf-8')


def case(doc,arm):
    envelope=load(f'{doc}/{arm}-response.json')
    return (load(f'{doc}/document.txt'), load(f'{doc}/candidates.json'),
            json.loads(envelope['choices'][0]['message']['content'])['assessments'],
            [r['server'] for r in load(f'{doc}/{arm}-assessment.json')['rows']])


def legacy_decision():
    # A hash-checked snapshot of our previous server function, not model text.
    namespace={'AXES':AXES,'__builtins__':{'any':any}}
    exec(compile(load('decision-before.py.txt'),'<frozen previous server>','exec'),namespace)
    return namespace['_decision']


def unreviewed_boundary(document,records,contract):
    """Boundary-only input: unknown review never becomes a fabricated success.

    The real pipeline requires review before calling this boundary. We neither
    run it nor invent its result: all fields are unresolved and no review is
    supplied here. Only the supplied tentative occurrence is projected.
    """
    frozen={'candidates':[dict(id=r['id'],**r['candidate']) for r in records],'rejected':[]}
    result=project_candidate_profile(document,'SYNTHETIC-BOUNDARY-D2',frozen,semantic_labels(records),coverage_verified=False)
    result.update(outcome='needs_confirmation',unresolvedFields=list(FIELDS),candidateCount=len(records),
                  rejectedReasons={},reviewIssueCount=0,modelDecisions=deepcopy(records))
    if contract=='confirmation-v3': result['reviewDispositions']=[]
    return project_candidate_confirmation(document,'SYNTHETIC-BOUNDARY-D2',result,contract=contract)
