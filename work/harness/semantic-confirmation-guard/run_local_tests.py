"""Keep noisy unittest output local; print only exit status and final diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / '.superpowers/sdd/plan-semantic-confirmation-guard'
OUT.mkdir(parents=True, exist_ok=True)
suite = sys.argv[1]
if suite not in ('tests', 'contract_tests'):
    raise ValueError('invalid suite')
log = OUT / (suite + '-' + sys.argv[2] + '.txt')
env = dict(os.environ, PYTHONIOENCODING='utf-8')
with log.open('x', encoding='utf-8') as stream:
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', suite, '-q'],
                            cwd=ROOT / 'ai_service', env=env, stdout=stream, stderr=subprocess.STDOUT)
text = log.read_text(encoding='utf-8')
print(json.dumps({'suite': suite, 'exit_code': result.returncode, 'log': str(log)}))
print(text[-3500:].encode('ascii', errors='backslashreplace').decode('ascii'))
sys.exit(result.returncode)
