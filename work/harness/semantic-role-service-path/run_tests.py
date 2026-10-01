"""Bounded local test runner; full output retained separately."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
suite, label = sys.argv[1:3]
pattern = sys.argv[3] if len(sys.argv) == 4 else 'test*.py'
if suite not in ('tests', 'runtime_tests', 'core_flow_tests', 'contract_tests') or not label.replace('-', '').isalnum():
    raise ValueError('invalid test options')
log = Path('E:/AgentFit/output/semantic-role-service-path-v1') / (label + '.log')
with log.open('xb') as stream:
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', suite, '-p', pattern],
                            cwd=ROOT / 'ai_service', stdout=stream, stderr=subprocess.STDOUT, timeout=900)
print(log.read_text(encoding='utf-8', errors='replace')[-5000:])
print('log:', log)
raise SystemExit(result.returncode)
