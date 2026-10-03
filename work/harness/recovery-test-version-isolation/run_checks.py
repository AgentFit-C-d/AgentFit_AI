"""Local-only regression runner with immutable logs and external socket guard."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('E:/AgentFit/output/recovery-test-version-isolation-20261003-v1')
GUARD = ROOT/'work/harness/tentative-proposed-preservation/offline_guard'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    OUT.mkdir(exist_ok=False)
    protected = {}
    for folder in ('ai_service/agentfit_ai', 'ai_service/diagnostic_tools',
                   'ai_service/tests/fixtures/review_recovery', 'ai_service/tests/fixtures/tentative_proposed'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                protected[str(path)] = sha(path)
    retained = json.loads((ROOT/'ai_service/tests/fixtures/tentative_proposed/manifest.json').read_bytes())
    for path, expected in retained['protectedFiles'].items():
        assert sha(Path(path)) == expected, path
        protected[path] = expected
    with (OUT/'protected-before.json').open('x', encoding='utf-8') as stream:
        json.dump(protected, stream, indent=2)
    with (OUT/'test_review_recovery.before.py').open('xb') as stream:
        stream.write((ROOT/'ai_service/tests/test_review_recovery.py').read_bytes())
    print(json.dumps({'protectedFiles': len(protected), 'output': str(OUT)}))


def run(folder, pattern):
    if folder not in ('tests', 'runtime_tests', 'core_flow_tests', 'contract_tests'):
        raise ValueError('invalid test directory')
    if not pattern.startswith('test_') or not pattern.endswith('.py') or '/' in pattern or '\\' in pattern:
        raise ValueError('invalid test pattern')
    stamp = datetime.now(timezone.utc).strftime('%H%M%S%f')
    env = os.environ.copy()
    for key in list(env):
        if key.endswith('_API_KEY'): env.pop(key)
    env['PYTHONPATH'] = os.pathsep.join([str(GUARD), str(ROOT/'ai_service'), str(ROOT/'ai_service/tests')])
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    reports = OUT/('cases-'+stamp)
    reports.mkdir(exist_ok=False)
    env['RECOVERY_TEST_REPORT_DIR'] = str(reports)
    proof = "import socket\ntry: socket.getaddrinfo('example.invalid',443)\nexcept OSError as e: assert str(e)=='EXTERNAL_NETWORK_FORBIDDEN'\nelse: raise AssertionError('external guard absent')"
    subprocess.run(['rtk', 'proxy', sys.executable, '-X', 'utf8', '-c', proof], env=env, check=True, timeout=10)
    command = ['rtk', 'proxy', sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', folder, '-p', pattern, '-v']
    log = OUT/('tests-'+stamp+'.txt')
    with log.open('x', encoding='utf-8') as stream:
        result = subprocess.run(command, cwd=ROOT/'ai_service', env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    with (OUT/('tests-'+stamp+'.json')).open('x', encoding='utf-8') as stream:
        json.dump({'command': command, 'returncode': result.returncode, 'externalGuard': True,
                   'modelCalls': 0, 'log': str(log), 'caseReports': str(reports)}, stream, indent=2)
    print(json.dumps({'returncode': result.returncode, 'log': str(log), 'caseReports': str(reports)}))
    return result.returncode


if __name__ == '__main__':
    if sys.argv[1:] == ['freeze']:
        freeze()
    else:
        raise SystemExit(run(sys.argv[1] if len(sys.argv)>1 else 'tests', sys.argv[2] if len(sys.argv)>2 else 'test_*.py'))
