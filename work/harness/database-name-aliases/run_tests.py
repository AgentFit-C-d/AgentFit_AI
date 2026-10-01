"""Run local unittest suites with a bounded duration and persistent evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[3]
out = Path('E:/AgentFit/output/database-name-aliases-v1')
label, suite, *patterns = sys.argv[1:]
command = [sys.executable, '-m', 'unittest', 'discover', '-s', suite, '-q']
if patterns:
    command += ['-p', patterns[0]]
env = {k: v for k, v in os.environ.items() if not k.endswith('_API_KEY')}
env['PYTHONIOENCODING'] = 'utf-8'
result = subprocess.run(command, cwd=repo / 'ai_service', env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
with (out / (label + '.log')).open('xb') as stream:
    stream.write(result.stdout)
print(result.stdout.decode('utf-8', errors='replace')[-5000:])
print(json.dumps({'label': label, 'exit_code': result.returncode, 'command': command}))
sys.exit(result.returncode)
