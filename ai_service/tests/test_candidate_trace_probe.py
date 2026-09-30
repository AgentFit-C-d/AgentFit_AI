"""Frozen, cost-bounded diagnostics; only the external scored call is substituted."""
import asyncio
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai import nvidia_evaluation_inputs as inputs
from agentfit_ai.analysis_call_metadata import build_metadata
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.independent_profile_evaluation import score_confirmation
from agentfit_ai.nvidia_evaluation_runner import _failure
from agentfit_ai.profile import FIELDS
from diagnostic_tools.candidate_trace import CandidateTrace
from diagnostic_tools.candidate_trace_worker import VERSION, MODEL
from tests.independent_evaluation_fixtures import write_json
from tests.nvidia_evaluation_fixtures import make_access
from tests.test_analysis_call_metadata import call
from tests.test_nvidia_review_evaluation import selected_variant

KEY = 'synthetic-nvidia-secret'


def api_module():
    try:
        return importlib.import_module('diagnostic_tools.candidate_trace_probe')
    except ModuleNotFoundError as error:
        if error.name != 'diagnostic_tools.candidate_trace_probe':
            raise
        raise AssertionError('candidate probe runner is not implemented') from None


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = api_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.enterContext(patch.object(inputs, 'ROOT', self.root))
        self.paths, _ = selected_variant(self.root)
        self.tools = self.root / 'ai_service/diagnostic_tools'
        self.tools.mkdir()
        (self.tools / '__init__.py').write_bytes(b'# synthetic tool\n')
        self.enterContext(patch.object(self.api, 'TOOLS', self.tools))
        self.prepared = self.api.prepare_probe(*self.paths)
        self.access = make_access(self.root / 'access.json')
        self.output = self.root / 'results'
        self.invocations = []

    async def provider(self, document, ident, gold, key, *, timeout_seconds, command,
                       call_diagnostics, review_model):
        self.assertEqual((key, review_model), (KEY, MODEL))
        self.assertEqual(timeout_seconds, 1800)
        self.assertEqual(command[1:3], ['-m', 'diagnostic_tools.candidate_trace_worker'])
        self.assertEqual(len(command), 4)
        for secret in (key, document, json.dumps(gold)):
            self.assertNotIn(secret, repr(command))
        self.invocations.append(ident)
        trace = CandidateTrace(document, ident)
        frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 5}], 'rejected': []}
        labels = [{'id': 'C000', 'field': 'frontend', 'status': 'confirmed'}]
        trace.observe('grounded', frozen)
        trace.observe('classified', {'frozen': frozen, 'labels': labels})
        result = finalize_candidate_analysis(document, ident, frozen, labels,
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []}, observer=trace.observe)
        trace.finish(result)
        write_json(Path(command[-1]), {'version': VERSION, 'documentId': ident,
            'sourceSha256': hashlib.sha256(document.encode()).hexdigest(),
            'status': 'available', 'error': None, 'trace': trace.summary()})
        call_diagnostics.update(build_metadata([dict(call(), transport_completed=True,
            response_bytes=100, provider_error=None)]))
        return score_confirmation(document, ident, gold, project_candidate_confirmation(document, ident, result))

    async def run_probe(self, provider=None):
        with patch.object(self.api, 'run_scored_process', side_effect=provider or self.provider):
            return await self.api.run_probe(self.prepared, self.output, KEY, self.access)

    def test_offline_cli_hashes_tools_without_reading_keys_or_changing_baseline(self):
        snapshots = [p.read_bytes() for p in self.paths]
        args = [part for name, path in zip(('corpus', 'gold', 'freeze'), self.paths)
                for part in ('--'+name, str(path))]
        out = io.StringIO()
        with patch.object(self.api, 'load_nvidia_key', side_effect=AssertionError('read key')), patch.object(
                self.api, 'run_probe', side_effect=AssertionError('launched')), redirect_stdout(out):
            self.assertEqual(self.api.main(args), 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report['cases'], ['PUBLIC-01', 'PUBLIC-09', 'PUBLIC-07'])
        self.assertEqual(report['mode'], 'preflight')
        self.assertFalse(report['release_gate_passed'])
        self.assertEqual(self.prepared['baseline']['metadata']['runs_per_case'], 3)
        self.assertEqual(self.prepared['metadata']['runs_per_case'], 1)
        self.assertEqual(set(self.prepared['metadata']['tool_files']), {'__init__.py'})
        self.assertEqual(snapshots, [p.read_bytes() for p in self.paths])
        self.assertFalse(self.output.exists())
        self.assertNotIn('React', out.getvalue())

    async def test_three_ordered_rows_keep_original_scores_and_bind_trace_identity(self):
        summary = await self.run_probe()
        self.assertEqual(self.invocations, ['PUBLIC-01', 'PUBLIC-09', 'PUBLIC-07'])
        self.assertEqual(summary['completed'], 3)
        self.assertEqual(summary['reserved_model_calls_upper_bound'], 192)
        self.assertEqual(summary['observed_calls'], 3)
        self.assertFalse(summary['human_reviewed'])
        self.assertFalse(summary['release_gate_passed'])
        manifest = json.loads((self.output / 'experiment.json').read_text())
        self.assertEqual(manifest, self.prepared['metadata'])
        for ident in self.invocations:
            row = json.loads((self.output / f'{ident}-run-0.json').read_text())
            self.assertEqual(row['score']['fields']['frontend']['matched'], 1)
            self.assertEqual(row['probe']['documentId'], ident)
            self.assertEqual(row['tool_sha256'], manifest['tool_sha256'])
        saved = ''.join(p.read_text() for p in self.output.iterdir())
        for private in ('React', KEY, 'SYNTHETIC TEST ONLY'):
            self.assertNotIn(private, saved)

    async def test_existing_output_and_started_only_are_preserved_without_replay(self):
        self.output.mkdir()
        for name in ('PUBLIC-01-run-0.started.json', 'PUBLIC-01-run-0.trace.json'):
            (self.output / name).write_bytes(b'{')
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
            await self.run_probe()
        self.assertEqual(self.invocations, [])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    async def test_partial_missing_or_forged_trace_never_becomes_terminal_success(self):
        for kind in ('partial', 'missing', 'identity', 'raw-key'):
            self.output = self.root / kind
            async def corrupt(*args, **options):
                score = await self.provider(*args, **options)
                path = Path(options['command'][-1])
                if kind == 'partial':
                    path.write_bytes(b'{')
                elif kind == 'missing':
                    path.unlink()
                else:
                    report = json.loads(path.read_text())
                    report['documentId' if kind == 'identity' else 'raw'] = 'PUBLIC-02' if kind == 'identity' else 'private-error'
                    write_json(path, report)
                return score
            before = len(self.invocations)
            with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
                await self.run_probe(corrupt)
            self.assertEqual(len(self.invocations) - before, 1)
            self.assertTrue((self.output / 'PUBLIC-01-run-0.started.json').exists())
            self.assertFalse((self.output / 'PUBLIC-01-run-0.json').exists())

    async def test_tool_drift_before_or_during_call_prevents_mixed_checkpoint(self):
        (self.tools / 'added.py').write_bytes(b'# changed')
        with self.assertRaisesRegex(ValueError, '^EXPERIMENT_CHANGED$'):
            await self.run_probe()
        self.assertEqual(self.invocations, [])
        self.prepared = self.api.prepare_probe(*self.paths)
        async def changed(*args, **options):
            result = await self.provider(*args, **options)
            (self.tools / 'added.py').write_bytes(b'# changed again')
            return result
        with self.assertRaisesRegex(ValueError, '^EXPERIMENT_CHANGED$'):
            await self.run_probe(changed)
        self.assertEqual(len(self.invocations), 1)
        self.assertFalse((self.output / 'PUBLIC-01-run-0.json').exists())

    async def test_baseline_or_in_memory_source_change_is_rejected_before_call(self):
        changed = deepcopy(self.prepared)
        changed['baseline']['cases'][0]['document'] += ' changed'
        with patch.object(self.api, 'run_scored_process', side_effect=self.provider):
            with self.assertRaisesRegex(ValueError, '^EXPERIMENT_CHANGED$'):
                await self.api.run_probe(changed, self.output, KEY, self.access)
        (self.root / 'ai_service/agentfit_ai/base.py').write_bytes(b'# drift')
        with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
            await self.run_probe()
        self.assertEqual(self.invocations, [])

    async def test_free_scope_expiry_and_budget_stop_before_first_or_next_call(self):
        for changes in ({'expires_at': '2000-01-01T00:00:00+00:00'}, {'models': ['paid-model']},
                        {'confirmed_no_additional_charge': False}):
            make_access(self.access, **changes)
            with self.assertRaisesRegex(ValueError, '^FREE_ACCESS_UNCONFIRMED$'):
                await self.run_probe()
        self.assertEqual(self.invocations, [])
        for kind, error in (('budget', 'FREE_ACCESS_BUDGET_EXHAUSTED'), ('expiry', 'FREE_ACCESS_UNCONFIRMED')):
            self.output = self.root / kind
            make_access(self.access, max_model_calls=64 if kind == 'budget' else 1920)
            async def expire(*args, **options):
                result = await self.provider(*args, **options)
                if kind == 'expiry':
                    make_access(self.access, expires_at='2000-01-01T00:00:00+00:00')
                return result
            before = len(self.invocations)
            with self.assertRaisesRegex(ValueError, '^'+error+'$'):
                await self.run_probe(expire)
            self.assertEqual(len(self.invocations) - before, 1)
            self.assertTrue((self.output / 'PUBLIC-01-run-0.json').exists())
            self.assertFalse((self.output / 'PUBLIC-09-run-0.started.json').exists())

    async def test_provider_error_is_recorded_and_stops_without_retry(self):
        async def failed(document, ident, gold, key, **options):
            self.invocations.append(ident)
            options['call_diagnostics'].update(build_metadata([call()], 'EXTRACTION_FAILED'))
            trace = CandidateTrace(document, ident).summary()
            write_json(Path(options['command'][-1]), {'version': VERSION, 'documentId': ident,
                'sourceSha256': trace['sourceSha256'], 'status': 'available', 'error': None, 'trace': trace})
            return _failure(document, ident, gold, 'PROVIDER_UNAVAILABLE')
        with self.assertRaisesRegex(ValueError, '^EVALUATION_PROVIDER_STOPPED$'):
            await self.run_probe(failed)
        self.assertEqual(self.invocations, ['PUBLIC-01'])
        saved = json.loads((self.output / 'PUBLIC-01-run-0.json').read_text())
        self.assertEqual(saved['score']['error'], 'PROVIDER_UNAVAILABLE')
        self.assertEqual(saved['probe']['trace']['status'], 'partial')
        self.assertFalse((self.output / 'PUBLIC-09-run-0.started.json').exists())

    async def test_cancellation_leaves_started_only_and_blocks_new_run(self):
        async def cancelled(*args, **options):
            raise asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.run_probe(cancelled)
        self.assertTrue((self.output / 'PUBLIC-01-run-0.started.json').exists())
        self.assertFalse((self.output / 'PUBLIC-01-run-0.json').exists())
        with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
            await self.run_probe()
        self.assertEqual(self.invocations, [])

    async def test_total_wall_budget_blocks_call_after_expiry(self):
        with patch.object(self.api, 'monotonic', side_effect=[0, 5401]):
            with self.assertRaisesRegex(ValueError, '^PROBE_BUDGET_EXHAUSTED$'):
                await self.run_probe()
        self.assertEqual(self.invocations, [])

    async def test_worker_fsync_failure_preserves_score_but_stops_before_terminal(self):
        from agentfit_ai import candidate_service_worker as service
        from diagnostic_tools import candidate_trace_worker as worker
        from tests.test_candidate_trace_worker import fake_pipeline
        async def failed_write(document, ident, gold, key, **options):
            self.invocations.append(ident)
            packet = json.dumps({'document': document, 'documentId': ident, 'key': key,
                'mode': 'integrated-nvidia', 'diagnostics': 'analysis-call-metadata-v1', 'reviewModel': MODEL}).encode()
            with patch.object(service, 'find_spec', return_value=object()), patch.object(
                    service, 'analyze_nvidia_candidates', fake_pipeline([])), patch.object(
                    worker.os, 'fsync', side_effect=OSError('private-disk-error')):
                envelope = json.loads(worker.execute_probe_request(packet, Path(options['command'][-1])))
            self.assertEqual(envelope['result']['outcome'], 'needs_confirmation')
            options['call_diagnostics'].update(envelope['diagnostics'])
            return score_confirmation(document, ident, gold, envelope['result'])
        with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
            await self.run_probe(failed_write)
        self.assertEqual(self.invocations, ['PUBLIC-01'])
        self.assertFalse((self.output / 'PUBLIC-01-run-0.json').exists())
        self.assertFalse((self.output / 'PUBLIC-09-run-0.started.json').exists())

    def test_live_cli_reads_synthetic_key_only_after_free_scope_validation(self):
        env = self.root / 'synthetic.env'
        env.write_text('NVIDIA_API_KEY=' + KEY, encoding='utf-8')
        args = ['--live', '--env-file', str(env), '--output', str(self.output),
                '--access-confirmation', str(self.access)]
        args += [part for name, path in zip(('corpus', 'gold', 'freeze'), self.paths)
                 for part in ('--'+name, str(path))]
        make_access(self.access, confirmed_no_additional_charge=False)
        out = io.StringIO()
        with patch.object(self.api, 'load_nvidia_key', side_effect=AssertionError('key read early')), redirect_stdout(out):
            self.assertEqual(self.api.main(args), 1)
        self.assertEqual(json.loads(out.getvalue()), {'error': 'FREE_ACCESS_UNCONFIRMED'})
        make_access(self.access)
        out = io.StringIO()
        with patch.object(self.api, 'run_scored_process', side_effect=self.provider), redirect_stdout(out):
            self.assertEqual(self.api.main(args), 0)
        self.assertEqual(json.loads(out.getvalue())['completed'], 3)
        self.assertNotIn(KEY, out.getvalue())


if __name__ == '__main__':
    unittest.main()
