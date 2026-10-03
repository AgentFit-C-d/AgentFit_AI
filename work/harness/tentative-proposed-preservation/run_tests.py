"""Retain test logs; no credentials, model calls or external transmission."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path('E:/AgentFit/output/tentative-proposed-preservation-20261003-v1')
pattern=sys.argv[1] if len(sys.argv)>1 else 'test_*.py'
if not pattern.startswith('test_') or not pattern.endswith('.py') or '/' in pattern or '\\' in pattern:
    raise ValueError('invalid local test pattern')
stamp=datetime.now(timezone.utc).strftime('%H%M%S%f')
env=os.environ.copy()
for name in ('NVIDIA_API_KEY','UPSTAGE_API_KEY','OPENAI_API_KEY'): env.pop(name,None)
env['PYTHONPATH']=os.pathsep.join([str(Path(__file__).parent/'offline_guard'),str(ROOT/'ai_service'),str(ROOT/'ai_service/tests')])
env['PYTHONIOENCODING']='utf-8'
proof="import socket\ntry: socket.getaddrinfo('example.invalid',443)\nexcept OSError as e: assert str(e)=='EXTERNAL_NETWORK_FORBIDDEN'\nelse: raise AssertionError('external guard absent')\nprint('external guard verified')"
checked=subprocess.run(['rtk','proxy',sys.executable,'-X','utf8','-c',proof],env=env,capture_output=True,text=True,encoding='utf-8',timeout=10)
if checked.returncode: raise RuntimeError('OFFLINE_GUARD_FAILED')
command=['rtk','proxy',sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p',pattern,'-v']
log=OUT/f'tests-{stamp}.txt'
with log.open('x',encoding='utf-8') as f:
    f.write(checked.stdout+checked.stderr)
    result=subprocess.run(command,cwd=ROOT/'ai_service',env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
with (OUT/f'tests-{stamp}.json').open('x',encoding='utf-8') as f:
    json.dump({'command':command,'returncode':result.returncode,'externalGuard':True,'modelCalls':0,'log':str(log)},f,indent=2)
print(json.dumps({'returncode':result.returncode,'log':str(log)}),flush=True)
raise SystemExit(result.returncode)
