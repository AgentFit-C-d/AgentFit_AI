"""Test-only preserved-runtime launcher. Never changes or reseals the archive."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory, gettempdir
import uuid
import zipfile

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parents[1]
FIXTURE = TESTS/'fixtures/review_recovery'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserved_case_names():
    tree = ast.parse((TESTS/'recovery_preserved_cases.py').read_text(encoding='utf-8'))
    case = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ReviewRecoveryTests')
    names = [n.name for n in case.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    if not names or len(names) != len(set(names)):
        raise ValueError('INVALID_PRESERVED_TEST_SET')
    return sorted(names)


def unpack_origin(destination):
    """Validate both the container and each file before writing a fresh copy."""
    seal = json.loads((FIXTURE/'manifest.json').read_bytes())
    if digest(FIXTURE/'records.zip') != seal['archiveSha256']:
        raise ValueError('ARCHIVE_HASH_MISMATCH')
    with zipfile.ZipFile(FIXTURE/'records.zip') as archive:
        for name, expected in seal['files'].items():
            target = destination/name
            if Path(name).is_absolute() or '..' in Path(name).parts or not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('UNSAFE_FIXTURE_PATH')
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('FIXTURE_HASH_MISMATCH')
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
    return seal


def save_artifact(name, data):
    target = os.environ.get('RECOVERY_TEST_REPORT_DIR')
    if target:
        folder = Path(target)
        if not folder.is_dir():
            raise ValueError('MISSING_TEST_REPORT_DIRECTORY')
        with (folder/(uuid.uuid4().hex+'-'+name)).open('xb') as stream:
            stream.write(data)


def run_preserved_suite():
    original_hashes = {p: digest(p) for p in (FIXTURE/'records.zip', FIXTURE/'manifest.json')}
    with TemporaryDirectory(prefix='agentfit-preserved-recovery-') as temporary:
        folder = Path(temporary).resolve()
        if not folder.is_relative_to(Path(gettempdir()).resolve()):
            raise ValueError('UNSAFE_TEMP_DIRECTORY')
        origin = folder/'origin'
        origin.mkdir()
        unpack_origin(origin)
        runtime = origin/'code-snapshot'
        freeze = json.loads((origin/'freeze.json').read_bytes())
        for name, expected in freeze['actualWorkingFileHashes'].items():
            if digest(runtime/name) != expected:
                raise ValueError('SNAPSHOT_HASH_MISMATCH')
        # The inspector was written after the live run. Copy it separately,
        # unchanged; it still validates the exact frozen analysis modules.
        inspector = ROOT/'ai_service/diagnostic_tools/review_recovery.py'
        destination = runtime/'ai_service/diagnostic_tools/review_recovery.py'
        if destination.exists():
            raise ValueError('INSPECTOR_WOULD_OVERWRITE_SNAPSHOT')
        shutil.copyfile(inspector, destination)
        tests = runtime/'ai_service/tests'
        tests.mkdir(exist_ok=False)
        for name in ('recovery_preserved_cases.py', 'recovery_preserved_worker.py', 'review_preservation_fixture.py',
                     'tentative_proposed_fixture.py', 'test_mention_role_cause.py',
                     'test_document_profile_v3_observer.py'):
            shutil.copyfile(TESTS/name, tests/name)
        shutil.copytree(FIXTURE, tests/'fixtures/review_recovery')
        for name in ('review_preservation', 'tentative_proposed'):
            shutil.copytree(TESTS/'fixtures'/name, tests/'fixtures'/name)
        env = os.environ.copy()
        for key in list(env):
            if key.endswith('_API_KEY'):
                env.pop(key)
        env['PYTHONPATH'] = os.pathsep.join([str(runtime/'ai_service'), str(tests)])
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        output = folder/'results.json'
        # shell=False: use this interpreter directly; CI needs no developer CLI.
        command = [sys.executable, '-X', 'utf8', str(tests/'recovery_preserved_worker.py'), str(output)]
        result = subprocess.run(command, cwd=runtime/'ai_service', env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=180)
        save_artifact('preserved-stdout.txt', (result.stdout+result.stderr).encode('utf-8'))
        if not output.is_file():
            raise RuntimeError('PRESERVED_WORKER_NO_REPORT: '+result.stdout+result.stderr)
        raw = output.read_bytes()
        save_artifact('preserved-results.json', raw)
        report = json.loads(raw)
        expected = preserved_case_names()
        if (report['testsRun'] != len(expected) or sorted(report['cases']) != expected or
                report['duplicates'] or not report['networkBlocked'] or
                report['runtime'] != str(runtime.resolve()) or
                report['inspectorSha256'] != digest(inspector)):
            raise AssertionError('INCOMPLETE_OR_WRONG_VERSION_TEST_REPORT')
        for name, expected_hash in freeze['actualWorkingFileHashes'].items():
            if digest(runtime/name) != expected_hash:
                raise AssertionError('PRESERVED_RUNTIME_CHANGED')
        if result.returncode != (0 if all(r['status'] in ('success', 'skip') for r in report['cases'].values()) else 1):
            raise AssertionError('INCONSISTENT_WORKER_EXIT')
        for path, expected_hash in original_hashes.items():
            if digest(path) != expected_hash:
                raise AssertionError('ORIGINAL_FIXTURE_CHANGED')
        return report['cases']
