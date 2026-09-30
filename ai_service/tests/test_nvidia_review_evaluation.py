"""Selected reviewers get isolated frozen evaluation identities and strict rows."""
import asyncio
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai import nvidia_evaluation_inputs as inputs, nvidia_evaluation_runner as runner
from agentfit_ai.analysis_call_metadata import build_metadata
from tests.independent_evaluation_fixtures import write_json
from tests.nvidia_evaluation_fixtures import make_access
from tests.test_analysis_call_metadata import call
import tests.test_nvidia_evaluation as legacy
import tests.test_nvidia_evaluation_diagnostics as diagnostics

DEEPSEEK = 'deepseek-ai/deepseek-v4.1-flash'
GLM = 'z-ai/glm-5.3'


def selected_variant(temp):
    original, _ = diagnostics.variant(temp)
    chosen = Path(temp)/'deepseek-review-freeze.json'
    write_json(chosen, inputs.build_freeze(original[0], original[1],
                                         call_diagnostics=True, review_model=DEEPSEEK))
    return (original[0], original[1], chosen), original


class ReviewPreflightTests(unittest.TestCase):
    def test_frozen_choice_and_cli_are_distinct_while_explicit_glm_matches_default(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            selected, original = selected_variant(temp)
            chosen = inputs.prepare_evaluation(*selected, call_diagnostics=True, review_model=DEEPSEEK)
            baseline = inputs.prepare_evaluation(*original, call_diagnostics=True)
            self.assertEqual(chosen['metadata']['variant'], 'nvidia-deepseek-review-v1')
            self.assertEqual(chosen['metadata']['settings']['review_model'], DEEPSEEK)
            self.assertEqual(baseline, inputs.prepare_evaluation(*original, call_diagnostics=True, review_model=GLM))
            for paths, model in ((selected, None), (original, DEEPSEEK)):
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
                    inputs.prepare_evaluation(*paths, call_diagnostics=True, review_model=model)
            args = ['--call-diagnostics', '--review-model', DEEPSEEK] + [
                part for name, path in zip(('corpus','gold','freeze'), selected)
                for part in ('--'+name, str(path))]
            output = io.StringIO()
            with patch.object(runner, 'load_nvidia_key', side_effect=AssertionError('read key')), patch.object(
                    runner, 'evaluate', side_effect=AssertionError('called provider')), redirect_stdout(output):
                self.assertEqual(runner.main(args), 0)
            self.assertEqual(json.loads(output.getvalue())['metadata'], chosen['metadata'])

    def test_invalid_choice_and_diagnosticsless_live_run_never_load_key(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            original, _ = diagnostics.variant(temp)
            for model, enabled in ((DEEPSEEK, False), (GLM, False), ('private', True),
                                   ('moonshotai/kimi-k3', True), (True, True), ([], True)):
                with self.subTest(model=model), self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
                    inputs.build_freeze(original[0], original[1], call_diagnostics=enabled, review_model=model)
            args = ['--live', '--review-model', DEEPSEEK] + [
                part for name, path in zip(('corpus','gold','freeze'), original)
                for part in ('--'+name, str(path))]
            output = io.StringIO()
            with patch.object(runner, 'load_nvidia_key', side_effect=AssertionError('read key')), patch.object(
                    runner, 'evaluate', side_effect=AssertionError('called provider')), redirect_stdout(output):
                self.assertEqual(runner.main(args), 1)
            self.assertEqual(json.loads(output.getvalue()), {'error': 'INVALID_EVALUATION_PREFLIGHT'})


class ReviewCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def success(self, doc, ident, gold, key, *, call_diagnostics, review_model):
        self.assertEqual(review_model, DEEPSEEK)
        rows = [dict(call(i), stage=stage, transport_completed=True, response_bytes=100, provider_error=None)
                for i, stage in ((1, 'EXTRACTION_FAILED'), (2, 'COVERAGE_REVIEW_FAILED'))]
        call_diagnostics.update(build_metadata(rows))
        return await legacy.NvidiaCheckpointTests.success(self, doc, ident, gold, key)

    async def test_selected_checkpoint_replay_and_wrong_model_or_manifest_rejection(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            paths, original = selected_variant(temp)
            prepared = inputs.prepare_evaluation(*paths, call_diagnostics=True, review_model=DEEPSEEK)
            output, access = Path(temp)/'results', make_access(Path(temp)/'access.json')
            with patch.object(runner, 'run_scored_process', side_effect=self.success) as calls:
                summary = await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
            self.assertEqual(calls.call_count, 30)
            self.assertEqual((summary['variant'], summary['version']),
                ('nvidia-deepseek-review-v1', 'nvidia-deepseek-review-evaluation-summary-v1'))
            self.assertEqual(summary['fields']['frontend']['matched'], 30)
            snapshots = {p.name: p.read_bytes() for p in output.iterdir()}
            with patch.object(runner, 'run_scored_process', side_effect=AssertionError('replayed')):
                self.assertEqual(await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access), summary)
                baseline = inputs.prepare_evaluation(*original, call_diagnostics=True)
                with self.assertRaisesRegex(ValueError, '^EXPERIMENT_CHANGED$'):
                    await runner.evaluate(baseline, output, 'synthetic-nvidia-secret', access)
                first = output/'PUBLIC-01-run-0.json'
                for index in (0, 1):
                    row = json.loads(snapshots[first.name])
                    row['diagnostics']['calls'][index]['requested_model'] = GLM
                    write_json(first, row)
                    with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
                        await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                    first.write_bytes(snapshots[first.name])
            self.assertEqual(snapshots, {p.name: p.read_bytes() for p in output.iterdir()})

    async def test_selected_provider_failure_stops_once_and_tampered_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            paths, _ = selected_variant(temp)
            prepared = inputs.prepare_evaluation(*paths, call_diagnostics=True, review_model=DEEPSEEK)
            output, access = Path(temp)/'results', make_access(Path(temp)/'access.json')
            async def failed(doc, ident, gold, key, *, call_diagnostics, review_model):
                self.assertEqual(review_model, DEEPSEEK)
                call_diagnostics.update(build_metadata([dict(call(), stage='COVERAGE_REVIEW_FAILED')],
                                                       'COVERAGE_REVIEW_FAILED'))
                return runner._failure(doc, ident, gold, 'PROVIDER_UNAVAILABLE')
            with patch.object(runner, 'run_scored_process', side_effect=failed) as calls:
                with self.assertRaisesRegex(ValueError, '^EVALUATION_PROVIDER_STOPPED$'):
                    await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
            self.assertEqual(calls.call_count, 1)
            with patch.object(runner, 'run_scored_process', side_effect=AssertionError('replayed')):
                with self.assertRaisesRegex(ValueError, '^EVALUATION_PROVIDER_STOPPED$'):
                    await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                path = output/'PUBLIC-01-run-0.json'
                row = json.loads(path.read_text())
                row['diagnostics']['calls'][0]['requested_model'] = GLM
                write_json(path, row)
                with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
                    await runner.evaluate(prepared, output, 'synthetic-nvidia-secret', access)


if __name__ == '__main__':
    unittest.main()
