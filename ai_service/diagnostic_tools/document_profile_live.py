"""One authorized, frozen NVIDIA evaluation; never imported by the HTTP service."""
import asyncio
from contextlib import suppress
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import monotonic

from agentfit_ai.analysis_process import run_analysis_process, AnalysisProcessError
from agentfit_ai.candidate_review_dispositions import REVIEW_CONTRACT
from agentfit_ai.deepseek_evaluation import ENDPOINT, MODEL
from agentfit_ai.solar import AnalysisError
from agentfit_ai.diagnostics import safe_code

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT/'ai_service'
ALLOWED_ENDPOINT = 'https://integrate.api.nvidia.com/v1/chat/completions'
ALLOWED_MODELS = (MODEL, 'z-ai/glm-5.3')
MAX_CALLS, TOTAL_SECONDS, PER_CALL_SECONDS, FINISH_RESERVE = 50, 1800, 600, 10


def save(path, value, *, replace=False):
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    if replace:
        temporary = path.with_suffix(path.suffix+'.new')
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    else:
        staged = path.with_suffix(path.suffix+'.staged')
        with staged.open('xb') as handle:
            handle.write(encoded)
        os.link(staged, path)  # Atomic publication, fail if final path already exists.
        staged.unlink()


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def actual_hashes():
    paths = []
    for directory in ('agentfit_ai', 'diagnostic_tools'):
        paths.extend(p for p in (SERVICE/directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix in ('.py', '.json', '.txt'))
    paths.extend(SERVICE.glob('requirements*.txt'))
    paths.extend((ROOT/'specs/ai-developer/document-profile-evaluation').glob('*.json'))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(set(paths))}


def verify_freeze(output):
    frozen = read(output/'freeze.json')
    if frozen is not None and (actual_hashes() != frozen['actualWorkingFileHashes'] or
            digest(Path(frozen['sourcePath'])) != frozen['sourceSha256'] or
            digest(Path(frozen['goldPath'])) != frozen['goldSha256']):
        raise AnalysisError('PROVIDER_FAILURE')


class RequestGuard:
    def __init__(self, send, deadline, output, *, clock=monotonic):
        self.send, self.deadline, self.output, self.clock = send, deadline, output, clock
        self.calls, self.stopped = [], False

    def __call__(self, payload, key, timeout):
        remaining = self.deadline-self.clock()
        if self.stopped or len(self.calls) >= MAX_CALLS or remaining <= 2:
            self.stopped = True
            raise AnalysisError('PROVIDER_TIMEOUT' if remaining <= 2 else 'PROVIDER_FAILURE')
        if (ENDPOINT != ALLOWED_ENDPOINT or payload.get('model') not in ALLOWED_MODELS or
                type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
            self.stopped = True
            raise AnalysisError('PROVIDER_MODEL')
        try:
            verify_freeze(self.output)
        except BaseException:
            self.stopped = True
            raise
        remaining = self.deadline-self.clock()
        if remaining <= 2:
            self.stopped = True
            raise AnalysisError('PROVIDER_TIMEOUT')
        limit = min(float(timeout), PER_CALL_SECONDS, remaining-2)
        started = self.clock()
        row = {'index': len(self.calls)+1, 'model': payload['model'], 'state': 'started',
               'pid': os.getpid(), 'remainingSecondsBeforeRequest': remaining, 'timeoutSeconds': limit,
               'requestDeadlineMonotonic': started+limit}
        self.calls.append(row)
        save(self.output/'request-journal.json', self.calls, replace=True)
        save(self.output/f'deadline-{row["index"]:03}.json', row)
        try:
            # Account for recording time too. The parent independently enforces this deadline.
            send_limit = min(limit, row['requestDeadlineMonotonic']-self.clock())
            if send_limit <= 0:
                raise AnalysisError('PROVIDER_TIMEOUT')
            result = self.send(payload, key, send_limit)
            if self.clock() >= row['requestDeadlineMonotonic']:
                raise AnalysisError('PROVIDER_TIMEOUT')
            row['state'] = 'completed'
            return result
        except BaseException as error:
            self.stopped = True
            row.update(state='failed', error=safe_code(getattr(error, 'code', None)))
            raise
        finally:
            row['elapsedSeconds'] = self.clock()-started
            save(self.output/'request-journal.json', self.calls, replace=True)
            save(self.output/f'deadline-{row["index"]:03}.complete.json', row)


def child(output, deadline):
    from agentfit_ai import candidate_service_worker
    from diagnostic_tools import document_profile_worker as observer
    base_recorder = observer.DocumentRecorder

    class CheckpointRecorder(base_recorder):
        def checkpoint(self):
            save(output/'trace-checkpoint.json', self.value, replace=True)

        def observe(self, *args, **kwargs):
            super().observe(*args, **kwargs)
            self.checkpoint()

        def transport(self, send):
            captured = super().transport(send)
            def recording(payload, key, timeout):
                # No headers/keys; use the existing bounded/redacting recorder.
                request = self.copy_record(payload)
                if request is None:
                    raise AnalysisError('PROVIDER_FAILURE')
                save(output/'active-request.json', {'index': len(self.value['calls'])+1,
                     'state': 'started', 'request': request}, replace=True)
                self.checkpoint()
                try:
                    return captured(payload, key, timeout)
                finally:
                    self.checkpoint()
            return recording

    observer.DocumentRecorder = CheckpointRecorder
    original = candidate_service_worker.analyze_nvidia_candidates
    def capped(*args, **kwargs):
        return original(*args, **kwargs, max_calls=MAX_CALLS)
    candidate_service_worker.analyze_nvidia_candidates = capped
    # Inline transport: the parent kills this same process, including its HTTP request.
    candidate_service_worker.post_nvidia_streaming_inline = RequestGuard(
        candidate_service_worker.post_nvidia_streaming_inline, deadline, output)
    raw = sys.stdin.buffer.read(observer.analysis_worker.MAX_INPUT_BYTES+1)
    sys.stdout.buffer.write(observer.execute_observed_request(raw, output/'trace.json'))


def run_once(document, key, output, *, total_seconds=TOTAL_SECONDS,
             finish_reserve=FINISH_RESERVE, command_builder=None):
    if (not 0 < finish_reserve < total_seconds <= TOTAL_SECONDS or output != output.resolve()):
        raise ValueError('invalid single-run limits')
    started = monotonic()
    stop_at = started+total_seconds-finish_reserve
    save(output/'execution-start.json', {'state': 'started', 'mode': 'integrated-nvidia',
         'nvidiaOnly': True, 'contract': REVIEW_CONTRACT, 'totalSeconds': total_seconds,
         'finishReserveSeconds': finish_reserve, 'analysisDeadlineMonotonic': stop_at,
         'maxCalls': MAX_CALLS, 'retries': 0})
    command = (command_builder(stop_at) if command_builder else
               [sys.executable, '-m', 'diagnostic_tools.document_profile_live',
                '--child', str(output), str(stop_at)])
    diagnostics, termination = {}, {}

    async def supervised():
        deadline = asyncio.get_running_loop().time()+max(0, stop_at-monotonic())
        task = asyncio.create_task(run_analysis_process(document, 'PUBLIC-01', key, deadline,
            nvidia_only=True, contract=REVIEW_CONTRACT, command=command, call_diagnostics=diagnostics))
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=.05)
                if done:
                    return await task
                # Immutable publications avoid Windows read/replace sharing races.
                deadlines = sorted(p for p in output.glob('deadline-*.json') if '.complete.' not in p.name)
                active = deadlines[-1] if deadlines else None
                expired = (active is not None and not active.with_suffix('.complete.json').exists() and
                           monotonic() >= read(active)['requestDeadlineMonotonic'])
                if expired:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task  # run_analysis_process kills and reaps before returning.
                    termination.update(error='PROVIDER_TIMEOUT', analysisProcessReaped=True)
                    raise AnalysisProcessError('PROVIDER_TIMEOUT')
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    try:
        result = asyncio.run(supervised())
    except AnalysisProcessError as error:
        result = {'contract': REVIEW_CONTRACT, 'outcome': 'failed', 'error': error.code}
        if error.code == 'ANALYSIS_DEADLINE_EXCEEDED':
            termination.update(error=error.code, analysisProcessReaped=True)
    except Exception:
        result = {'contract': REVIEW_CONTRACT, 'outcome': 'failed', 'error': 'LOCAL_EXECUTION_FAILED'}
    journal = read(output/'request-journal.json', [])
    if termination:
        termination['activeRequestIndex'] = journal[-1]['index'] if journal else None
        save(output/'termination.json', termination)
    save(output/'result.json', result)
    save(output/'call-metadata.json', diagnostics)
    save(output/'execution.json', {'state': 'finished', 'outcome': result.get('outcome'),
         'error': result.get('error'), 'requestAttempts': len(journal), 'retries': 0,
         'elapsedSeconds': monotonic()-started, 'traceAvailable': (output/'trace.json').exists(),
         'checkpointAvailable': (output/'trace-checkpoint.json').exists(),
         'limits': {'calls': MAX_CALLS, 'totalSeconds': total_seconds, 'perRequestSeconds': PER_CALL_SECONDS,
                    'finishReserveSeconds': finish_reserve}, 'contract': REVIEW_CONTRACT})
    return result


def prepare(output, source, baseline):
    spec = ROOT/'specs/ai-developer/document-profile-evaluation'
    gold = spec/'gold-draft.json'
    previous = read(baseline/'freeze.json')
    if digest(source) != previous['sourceSha256'] or digest(gold) != previous['goldSha256']:
        raise ValueError('source or gold changed')
    document = source.read_bytes().decode('utf-8')  # Preserve exact CR/LF and Unicode.
    if hashlib.sha256(document.encode('utf-8')).hexdigest() != previous['sourceSha256']:
        raise ValueError('input text changed')
    git = ['rtk', 'proxy', 'git', '-c', 'safe.directory='+str(ROOT), '-C', str(ROOT)]
    def state(*args):
        return subprocess.check_output(git+list(args), text=True, encoding='utf-8').strip()
    hashes = actual_hashes()
    output.mkdir(parents=True, exist_ok=False)
    for name, path in [('source.md', source), ('document.txt', source), ('gold.json', gold)]:
        shutil.copyfile(path, output/name)
    for name in hashes:
        target = output/'code-snapshot'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    packages = {}
    for name in ('langextract', 'httpx', 'pydantic', 'python-dotenv'):
        with suppress(importlib.metadata.PackageNotFoundError):
            packages[name] = importlib.metadata.version(name)
    save(output/'freeze.json', {'revision': state('rev-parse', 'HEAD'),
         'gitStatus': state('status', '--porcelain=v1', '--untracked-files=all'),
         'actualWorkingFileHashes': hashes, 'sourcePath': str(source), 'goldPath': str(gold),
         'sourceSha256': digest(source), 'goldSha256': digest(gold),
         'previousRevision': previous['revision'], 'pythonExecutable': sys.executable,
         'pythonSha256': digest(Path(sys.executable)), 'pythonVersion': sys.version, 'packages': packages,
         'endpoint': ENDPOINT, 'allowedModels': ALLOWED_MODELS, 'mode': 'integrated-nvidia',
         'contract': REVIEW_CONTRACT, 'nvidiaOnly': True, 'maxCalls': MAX_CALLS,
         'totalSeconds': TOTAL_SECONDS, 'perRequestSeconds': PER_CALL_SECONDS,
         'finishReserveSeconds': FINISH_RESERVE, 'retries': 0, 'firstFailureStops': True,
         'sourceOnlyInput': True, 'oldCandidatesInjected': False, 'goldSentToModel': False,
         'freeAccessBasis': 'User explicitly authorized previously confirmed free NVIDIA endpoints for this one run'})
    verify_freeze(output)
    return document


def main(output):
    from dotenv import dotenv_values
    document = prepare(output, Path('E:/AgentFit/Docs/project-proposal.md'),
                       Path('E:/AgentFit/output/document-profile-baseline-live-20261002-v1'))
    key = dotenv_values('E:/AgentFit/.env').get('NVIDIA_API_KEY')
    if not key:
        save(output/'execution.json', {'state': 'not_started', 'error': 'MISSING_NVIDIA_KEY', 'requestAttempts': 0})
        return
    run_once(document, key, output)
    verify_freeze(output)
    save(output/'integrity-after.json', {'codeSourceGoldUnchanged': True})
    print(json.dumps(read(output/'execution.json')))


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--child':
        child(Path(sys.argv[2]), float(sys.argv[3]))
    elif len(sys.argv) == 3 and sys.argv[1] == '--execute-approved-once':
        main(Path(sys.argv[2]).resolve())
    else:
        raise SystemExit('Explicit authorized single-run command required')
