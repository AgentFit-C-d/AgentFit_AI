"""Preserve production modules before changing the service entry point."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('E:/AgentFit/output/semantic-role-service-path-v1')
target = OUT / 'baseline/agentfit_ai'
if target.exists():
    raise ValueError('baseline already exists')
shutil.copytree(ROOT / 'ai_service/agentfit_ai', target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
hashes = {str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file()}
with (OUT / 'baseline.json').open('x', encoding='utf-8') as stream:
    json.dump({'baseCommit': '5de4020', 'files': hashes}, stream, indent=2)
print(json.dumps({'baselineFiles': len(hashes)}))
