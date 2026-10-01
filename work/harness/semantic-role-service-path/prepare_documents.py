"""Acquire a new pinned public README, keeping previous inputs untouched."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path('E:/AgentFit/output/semantic-role-service-path-v1')
COMMIT = '27b7303baf41bb28babc610ac8eaa486e1ddfab5'
url = f'https://raw.githubusercontent.com/sissbruecker/linkding/{COMMIT}/README.md'
with urlopen(Request(url, headers={'User-Agent': 'AgentFit-public-evaluation'}), timeout=30) as response:
    raw = response.read(100001)
if not 1 <= len(raw) <= 100000:
    raise ValueError('unexpected document size')
raw.decode('utf-8')
with (OUT / 'linkding.md').open('xb') as stream:
    stream.write(raw)
old = Path('E:/AgentFit/output/independent-profile-v1/PUBLIC-01.md').read_bytes()
with (OUT / 'documenso.md').open('xb') as stream:
    stream.write(old)
inputs = [{'id': 'documenso', 'file': 'documenso.md', 'sha256': hashlib.sha256(old).hexdigest(),
    'usage': 'existing regression document',
    'source': 'https://github.com/documenso/documenso/blob/a1d4bec1430a937395db9a4aae28979cd71c2831/README.md'},
    {'id': 'linkding', 'file': 'linkding.md', 'sha256': hashlib.sha256(raw).hexdigest(),
     'usage': 'new document, no matches in existing specs/harness/tests/output records before acquisition',
     'source': f'https://github.com/sissbruecker/linkding/blob/{COMMIT}/README.md'}]
with (OUT / 'documents.json').open('x', encoding='utf-8') as stream:
    json.dump({'documents': inputs, 'human_reviewed': False, 'pretraining_exposure': 'unknown'}, stream, indent=2)
print(json.dumps(inputs))
