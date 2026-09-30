"""Diagnostic variant isolation and durable, source-free evaluation checkpoints."""
import asyncio
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai import nvidia_evaluation_inputs as inputs, nvidia_evaluation_runner as runner
from agentfit_ai.analysis_call_metadata import METADATA_VERSION, build_metadata
from tests.nvidia_evaluation_fixtures import make_variant, make_access
from tests.independent_evaluation_fixtures import write_json
from tests.test_analysis_call_metadata import call
import tests.test_nvidia_evaluation as legacy


def variant(temp):
    corpus, gold, old_freeze = make_variant(temp)
    (Path(temp)/'ai_service/agentfit_ai/analysis_call_metadata.py').write_text('# synthetic metadata')
    new_freeze = Path(temp)/'diagnostic-freeze.json'
    write_json(new_freeze, inputs.build_freeze(corpus, gold, call_diagnostics=True))
    return (corpus, gold, new_freeze), old_freeze


class DiagnosticPreflightTests(unittest.TestCase):
    def test_opt_in_freeze_and_cli_separate_variant_without_api_or_keys(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            paths, old = variant(temp)
            prepared = inputs.prepare_evaluation(*paths, call_diagnostics=True)
            self.assertEqual(prepared['metadata']['variant'], 'nvidia-call-diagnostics-v1')
            self.assertEqual(prepared['metadata']['settings']['call_diagnostics'], METADATA_VERSION)
            for chosen, enabled in ((paths, False), ((paths[0], paths[1], old), True)):
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
                    inputs.prepare_evaluation(*chosen, call_diagnostics=enabled)
            args = ['--call-diagnostics'] + [part for name, path in zip(('corpus','gold','freeze'), paths)
                                            for part in ('--'+name, str(path))]
            out = io.StringIO()
            with patch.object(runner, 'load_nvidia_key', side_effect=AssertionError('key read')), patch.object(
                    runner, 'evaluate', side_effect=AssertionError('provider called')), redirect_stdout(out):
                code = runner.main(args)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())['metadata'], prepared['metadata'])
            with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
                inputs.build_freeze(paths[0], paths[1], call_diagnostics=1)


class DiagnosticCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def success(self, document, document_id, gold, key, *, call_diagnostics):
        call_diagnostics.update(build_metadata([dict(call(), transport_completed=True,
                                                    response_bytes=200, provider_error=None)]))
        return await legacy.NvidiaCheckpointTests.success(self, document, document_id, gold, key)

    async def test_thirty_scores_include_safe_metadata_and_resume_without_replay(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            paths, _ = variant(temp)
            prepared = inputs.prepare_evaluation(*paths, call_diagnostics=True)
            output, access = Path(temp)/'out', make_access(Path(temp)/'access.json')
            with patch.object(runner, 'run_scored_process', side_effect=self.success) as calls:
                result = await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
            self.assertEqual(calls.call_count, 30)
            self.assertEqual(result['variant'], 'nvidia-call-diagnostics-v1')
            self.assertEqual(result['fields']['frontend']['matched'], 30)
            rows = [json.loads(p.read_text()) for p in output.glob('PUBLIC-*-run-?.json')]
            self.assertEqual(len(rows), 30)
            self.assertTrue(all(r['diagnostics']['status'] == 'available' for r in rows))
            snapshots = {p.name: p.read_bytes() for p in output.iterdir()}
            for private in ('React', 'synthetic-nvidia-secret', 'SYNTHETIC TEST ONLY'):
                self.assertNotIn(private, repr(snapshots))
            with patch.object(runner, 'run_scored_process', side_effect=AssertionError('replayed')):
                self.assertEqual(await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access), result)
            self.assertEqual(snapshots, {p.name: p.read_bytes() for p in output.iterdir()})
            first = output/'PUBLIC-01-run-0.json'
            for mutation in ('missing', 'raw', 'index', 'stage'):
                row = json.loads(snapshots[first.name])
                if mutation == 'missing': row.pop('diagnostics')
                elif mutation == 'raw': row['diagnostics']['private'] = 'private-document'
                elif mutation == 'index': row['diagnostics']['calls'][0]['call_index'] = 2
                else: row['diagnostics']['failureStage'] = 'EXTRACTION_FAILED'
                write_json(first, row)
                with patch.object(runner, 'run_scored_process', side_effect=AssertionError('replayed')):
                    with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
                        await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                first.write_bytes(snapshots[first.name])

    async def test_failure_diagnostics_are_saved_once_and_stop_resume(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            paths, _ = variant(temp)
            prepared = inputs.prepare_evaluation(*paths, call_diagnostics=True)
            output, access = Path(temp)/'out', make_access(Path(temp)/'access.json')
            async def failed(doc, ident, gold, key, *, call_diagnostics):
                call_diagnostics.update(build_metadata([call()], 'EXTRACTION_FAILED'))
                return runner._failure(doc, ident, gold, 'PROVIDER_UNAVAILABLE')
            with patch.object(runner, 'run_scored_process', side_effect=failed) as calls:
                with self.assertRaisesRegex(ValueError, '^EVALUATION_PROVIDER_STOPPED$'):
                    await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
            self.assertEqual(calls.call_count, 1)
            saved = json.loads((output/'PUBLIC-01-run-0.json').read_text())
            self.assertEqual(saved['diagnostics']['calls'][0]['provider_error'], 'PROVIDER_UNAVAILABLE')
            self.assertEqual(saved['score']['fields']['frontend']['missing'], 1)
            with patch.object(runner, 'run_scored_process', side_effect=AssertionError('replayed')):
                with self.assertRaisesRegex(ValueError, '^EVALUATION_PROVIDER_STOPPED$'):
                    await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
            saved['score']['error'] = 'PROVIDER_RATE_LIMIT'
            write_json(output/'PUBLIC-01-run-0.json', saved)
            with patch.object(runner, 'run_scored_process', side_effect=AssertionError('replayed')):
                with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
                    await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)

    async def test_corrupt_metadata_is_not_persisted_and_started_only_blocks_replay(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
                paths, _ = variant(temp)
                prepared = inputs.prepare_evaluation(*paths, call_diagnostics=True)
                output, access = Path(temp)/'out', make_access(Path(temp)/'access.json')
                async def interrupted(*args, call_diagnostics):
                    if not corrupt:
                        raise asyncio.CancelledError
                    score = await self.success(*args, call_diagnostics=call_diagnostics)
                    call_diagnostics['private'] = 'source-only'
                    return score
                with patch.object(runner, 'run_scored_process', side_effect=interrupted):
                    with self.assertRaises(ValueError if corrupt else asyncio.CancelledError):
                        await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                self.assertFalse((output/'PUBLIC-01-run-0.json').exists())
                self.assertTrue((output/'PUBLIC-01-run-0.started.json').exists())
                self.assertNotIn('source-only', ''.join(p.read_text() for p in output.iterdir()))
                with patch.object(runner, 'run_scored_process', side_effect=AssertionError('replayed')):
                    with self.assertRaisesRegex(ValueError, '^INCOMPLETE_RUN$'):
                        await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)


if __name__ == '__main__':
    unittest.main()
