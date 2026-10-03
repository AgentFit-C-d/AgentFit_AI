"""Read-only artifact checks; write a new summary without replacing old runs."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'ai_service'), str(ROOT / 'ai_service/tests')]
from review_preservation_fixture import offline
from tentative_proposed_fixture import DIRECTORY, case
from agentfit_ai.candidate_semantic_assessment import check_decision_records

OUT = Path('E:/AgentFit/output/tentative-proposed-preservation-20261003-v1')

with offline():
    manifest = json.loads((DIRECTORY / 'manifest.json').read_bytes())
    for name, expected in manifest['files'].items():
        assert hashlib.sha256(gzip.decompress((DIRECTORY / (name + '.gz')).read_bytes())).hexdigest() == expected, name
    for name, expected in manifest['protectedFiles'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
    compatibility = []
    for doc in ('D1', 'D2'):
        for arm in ('A', 'B'):
            document, _, _, previous = case(doc, arm)
            try:
                check_decision_records(previous, document=document)
            except ValueError as error:
                status = str(error)
            else:
                status = 'accepted'
            assert status == ('accepted' if doc == 'D1' else 'INVALID_SEMANTIC_ASSESSMENT')
            compatibility.append({'document': doc, 'arm': arm, 'oldDerivedRecordsUnderNewValidator': status})
    after = json.loads((OUT / 'after.json').read_bytes())
    service = ROOT / 'ai_service/agentfit_ai/candidate_semantic_assessment.py'
    assert hashlib.sha256(service.read_bytes()).hexdigest() == after['serviceAfterSha256']
    summary = {
        'fixtureBlobsVerified': len(manifest['files']),
        'protectedFilesVerified': len(manifest['protectedFiles']),
        'unchangedSinceReplay': True,
        'compatibility': compatibility,
        'note': 'Historical derived decisions remain immutable. Revalidate raw responses into separate records; do not mix code versions.',
        'modelCalls': 0,
        'externalNetwork': 0,
    }
    with (OUT / 'final-verification.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))
