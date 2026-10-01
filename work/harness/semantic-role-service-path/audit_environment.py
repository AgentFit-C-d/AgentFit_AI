"""Print only whitelisted non-secret local settings and credential presence."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

settings = ('AGENTFIT_ANALYSIS_MODE', 'AGENTFIT_REQUEST_TIMEOUT_SECONDS',
            'AGENTFIT_MAX_INFLIGHT_ANALYSES', 'AGENTFIT_UPLOAD_TIMEOUT_SECONDS')
keys = ('AGENTFIT_INTERNAL_TOKEN', 'NVIDIA_API_KEY', 'UPSTAGE_API_KEY')
report = {'observedAt': datetime.now(timezone.utc).isoformat(),
          'processSettings': {name: os.environ.get(name) for name in settings},
          'processCredentialPresent': {name: bool(os.environ.get(name, '').strip()) for name in keys}}
env_file = Path('E:/AgentFit/.env')
found = {}
for line in env_file.read_text(encoding='utf-8-sig').splitlines() if env_file.exists() else []:
    name, sep, value = line.partition('=')
    name = name.strip()
    if sep and name in (*settings, *keys):
        found[name] = value.strip().strip('\"\'')
report['envFile'] = {'exists': env_file.exists(), 'automaticallyLoadedByService': False,
    'settings': {name: found.get(name) for name in settings},
    'credentialPresent': {name: bool(found.get(name)) for name in keys}}
out = Path('E:/AgentFit/output/semantic-role-service-path-v1')
out.mkdir(exist_ok=True)
with (out / 'environment.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False))
