"""Read existing call metadata; never sends network requests."""
import json
from pathlib import Path
from time import time

root = Path('E:/AgentFit/output/semantic-role-service-path-v1')
for folder in sorted(root.glob('live-*')):
    if not folder.is_dir():
        continue
    started = list(folder.glob('*-call-started.json'))
    completed = list(folder.glob('*-call.json'))
    last = json.loads(sorted(started)[-1].read_text(encoding='utf-8')) if started else None
    request = json.loads((folder / 'request-started.json').read_text(encoding='utf-8'))
    print(json.dumps({'request': folder.name, 'started_calls': len(started), 'returned_calls': len(completed),
        'last_started': last, 'elapsed_seconds': round(time() - request['time']),
        'response_saved': (folder / 'response.json').exists()}))
