"""Local only: retain full fresh test outputs; never imports live credentials."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
output=Path('E:/AgentFit/output')/f'role-context-ab-preflight-{stamp}'
output.mkdir(exist_ok=False)
rows=[]
for name in ('mention-role-guidance-ab/test_experiment.py','role-context-ab/test_context.py'):
    command=['rtk','proxy',sys.executable,str(ROOT/'work/harness'/name)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    dest=output/(Path(name).parent.name+'.txt')
    with dest.open('x',encoding='utf-8') as f: f.write(result.stdout+result.stderr)
    rows.append({'suite':name,'returncode':result.returncode,'log':str(dest)})
    print(name, 'exit=',result.returncode,flush=True)
with (output/'results.json').open('x',encoding='utf-8') as f: json.dump(rows,f,indent=2)
print(output,flush=True)
raise SystemExit(int(any(r['returncode'] for r in rows)))
