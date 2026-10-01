import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for name in ('semantic-confirmation-guard-v2', 'semantic-confirmation-guard-glm-v1'):
    output = Path('E:/AgentFit/output') / name
    freeze = json.loads((output / 'freeze.json').read_text(encoding='utf-8'))
    for path, digest in freeze['files'].items():
        raw = (ROOT / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest, path
        target = output / 'snapshot' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    print(name, 'snapshot preserved', len(freeze['files']))
