"""One-time local copy; never modifies historical runs or loads credentials."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'ai_service'),str(ROOT/'ai_service/tests')]
from review_preservation_fixture import offline

ORIGINAL=Path('E:/AgentFit/output/role-context-ab-20261003-v1')
DEST=ROOT/'ai_service/tests/fixtures/tentative_proposed'
def sha(raw): return hashlib.sha256(raw).hexdigest()

with offline():
    old=json.loads((ORIGINAL/'freeze.json').read_bytes())
    names=['freeze.json','suite.json','execution.json','calls.json','verification.json']
    for doc in ('D1','D2'):
        names += [f'{doc}/{n}' for n in ('document.txt','candidates.json','expected.json','A-response.json','B-response.json',
                                       'A-assessment.json','B-assessment.json','A-role-instruction.txt','B-role-instruction.txt')]
    blobs={name:(ORIGINAL/name).read_bytes() for name in names}
    for name,data in blobs.items():
        known=old['sha256'].get(str((ORIGINAL/name).resolve()))
        if known is not None: assert sha(data)==known, name
    service=ROOT/'ai_service/agentfit_ai/candidate_semantic_assessment.py'
    source=service.read_text('utf-8')
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_decision')
    blobs['decision-before.py.txt']=ast.get_source_segment(source,node).encode()
    DEST.mkdir(parents=True,exist_ok=False)
    for name,data in blobs.items():
        target=DEST/(name+'.gz'); target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f: f.write(gzip.compress(data,mtime=0))
    guardfiles={str(p):sha(p.read_bytes()) for p in ORIGINAL.rglob('*') if p.is_file()}
    guardfiles.update({str(p):sha(p.read_bytes()) for p in (ROOT/'ai_service/agentfit_ai/candidate_mention_roles.py',
        ROOT/'ai_service/agentfit_ai/candidate_confirmation.py',ROOT/'ai_service/agentfit_ai/semantic_confirmation_metadata.py',
        ROOT/'ai_service/agentfit_ai/candidate_analysis_pipeline.py',ROOT/'ai_service/agentfit_ai/candidate_review_dispositions.py',
        Path('E:/AgentFit/output/document-profile-v3-live-20261002-v1/gold.json'))})
    manifest={'sourceRun':str(ORIGINAL),'files':{n:sha(b) for n,b in blobs.items()},
              'serviceBeforeSha256':sha(service.read_bytes()),'protectedFiles':guardfiles,
              'modelCalls':0,'reviewResponsesAvailable':False}
    with (DEST/'manifest.json').open('x',encoding='utf-8') as f: json.dump(manifest,f,ensure_ascii=False,indent=2)
    print('Frozen files:',len(blobs),'; model calls: 0')
